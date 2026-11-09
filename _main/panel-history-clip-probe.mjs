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
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
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
const DAY = 86400000;
function at(msAgo, text, context) {
  const d = new Date(Date.now() - msAgo);
  const p = (n) => String(n).padStart(2, '0');
  const entry = {
    date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`,
    time: `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`,
    text,
    path: null,
  };
  if (context) entry.context = context;
  return entry;
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
/* O MESMO BRIDGE PARA AS DUAS CARGAS (2026-11-09): a janela de retencao e' uma
 * arm propria e precisa da pagina REAL outra vez, com o MESMO fake. Copiar o
 * bloco seria a duplicacao que o `code-health` conta. */
const FAKE_BRIDGE = ({ rows, hits }) => {
  /* THE SEARCH HITS ARE THE SHIPPED SEARCH'S OUTPUT, not a literal written
   * here: `_main/history-retention-fixture.py` builds a real history root, moves
   * a real written line 60 days back and answers `history_search` from the
   * shell's own method. This stub only CARRIES those hits across the bridge
   * boundary, and records every query the panel sends, so an arm can prove the
   * panel asked for the right thing. */
  const calls = [];
  window.__searchCalls = calls;
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
      search(query) {
        calls.push(String(query == null ? '' : query));
        const found = (hits && hits[query]) || [];
        return Promise.resolve({ hits: found });
      },
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
};
await ctx.addInitScript(FAKE_BRIDGE, { rows: entries, hits: {} });

const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto(PANEL, { waitUntil: 'load' });
await page.waitForFunction(
  () => document.querySelectorAll('#history-list .hist').length >= 3,
  null,
  { timeout: 15000 },
);

/* AS DUAS FOLHAS QUE CHEGAM POR PEDIDO (medido 2026-11-08).
 *
 * `panel.html` NAO liga `themes/cinematic.css` nem `themes/panel-designs.css`:
 * desde o `lazy-assets.js` elas chegam quando o shell pede um tema `cine-*` /
 * `pd-*`. Sem elas o probe media 30 dos 45 desenhos com a face de RECURSO
 * (Instrument Sans 13.5px) e chamava isso de "identidade" -- o artefacto era da
 * PAGINA do probe, nao do painel. Ligadas aqui, o medidor ve o mesmo documento
 * que o dono ve depois de escolher o tema. */
/* O BRAÇO NEGATIVO DESTE PROBE, SEM TOCAR NO FICHEIRO VIVO.
 * `SOTTO_PROBE_UNIFIED=<ficheiro.css>` entra como ULTIMA folha: e' assim que um
 * controlo passa a regra LITERAL de antes da cura (a mesma linha em todos os
 * temas) por cima do painel REAL e mede se o probe acusa. Escrever numa copia do
 * `panel-unified.css` e trocar o ficheiro vivo por um instante seria a outra via
 * -- e um painel aberto do dono pintaria a copia durante esse instante. */
/* `--neg-arm` REPOE A REGRA LITERAL DE ANTES DA CURA (a mesma linha, o mesmo
 * tamanho, a mesma entrelinha em TODOS os desenhos) e exige que o braco da
 * identidade caia. A convencao da casa: devolve rc=1 quando APANHA. */
const NEG_ARM = process.argv.includes('--neg-arm');
const LITERAL_BEFORE_THE_CURE = `html body[data-surface="panel"] .history__list .hist__text {
  font-family: "Instrument Sans", "Segoe UI Variable Text", "Segoe UI",
    system-ui, sans-serif !important;
  font-size: calc(13.5px * var(--caption-scale)) !important;
  line-height: 1.5 !important;
  font-weight: 400 !important;
  letter-spacing: normal !important;
  text-transform: none !important;
}`;
if (NEG_ARM) {
  await page.addStyleTag({ content: LITERAL_BEFORE_THE_CURE });
} else if (process.env.SOTTO_PROBE_UNIFIED) {
  const override = readFileSync(process.env.SOTTO_PROBE_UNIFIED, 'utf8');
  await page.addStyleTag({ content: override });
}
for (const href of ['themes/cinematic.css', 'themes/panel-designs.css']) {
  await page.evaluate((h) => new Promise((resolve) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = h;
    link.onload = resolve;
    link.onerror = resolve;
    document.head.appendChild(link);
  }), href);
}

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
      // A IDENTIDADE DO DESENHO, medida no RENDER (ordem do dono, 2026-11-08:
      // *"VOCE TIROU O DESIGN DE TODAS AS LEGENDAS PRA DEIXAR ELAS IGUAIS EM
      // TODOS OS TEMAS"*). Um tema que repita a familia+nome do outro e' a
      // mesma legenda outra vez.
      family: cs.fontFamily,
      fontSize: cs.fontSize,
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
/* THE 60-DAY ROW, IN THE REAL DOM -- RETAINED, VISIBLE, CONTEXTUAL, FINDABLE.
 *
 * Owner, 2026-11-09: months-later recall. `HISTORY_RETENTION_H` said 48 h while
 * `sotto_webview.HISTORY_RETENTION_H` kept 180 days, so the panel hid 178 days
 * the disk had. A predicate receipt is NOT a DOM pass: the earlier audit marked
 * "a 60-day row rendered in the real panel" UNMEASURED, and this is that arm.
 *
 * THE LINE IS REAL, AND SO IS THE SEARCH. `_main/history-retention-fixture.py`
 * appends through `SottoShell.history_append` (the shipped writer), moves the
 * hour file into a day folder 60 days back (and a second one 200 days back) and
 * answers `history_tail`/`history_search` from the shipped methods over that
 * root. This probe only carries those answers across the bridge and measures
 * the SHIPPED page: nothing about the SEARCH PREDICATE is re-implemented in
 * JavaScript, so a regression in it turns `searchCtx`/`searchNoLeak` RED.
 *
 * WHAT THIS GATE DOES NOT OWN: the STORE's own prune/retention. The fixture
 * pins `_history_pruned_stamp` so the prune is an explicit no-op -- the 200-day
 * folder has to stay on disk for the panel's filter to be provable -- and the
 * store's retention is measured by `_main/history-context-oracle.py` (s19-s21).
 * The near-edge row is what ties the panel's window to the SHELL's constant:
 * its age is `retention_h - 1 day`, read from the fixture, not written here.
 *
 * ARMS (all measured on the shipped `panel.html` + `panel.js`):
 *   feedCount     the feed paints exactly the entries the window admits
 *   feedSixty     the 60-day row is PRESENT and VISIBLE (box, computed style)
 *   feedNoLeak    the 200-day row is not in the feed
 *   ctxPaint      `data-context`, `li.title` and `.hist__text[title]` carry the
 *                 compact context, in the contract's order
 *   searchCtx     a context-ONLY query reaches the bridge once, and the hit is
 *                 painted with `.hist__ctx` and the matched word marked
 *   searchNoLeak  a query the store answers with the 200-day line paints NOTHING
 *
 * The expected summary is written here as a LITERAL on purpose: it is the
 * contract (`.agent-work/history-ui-contract.md` §3), not a copy of the code
 * being measured.
 */
const EXPECTED_CTX = 'device:mic · Code: main.py · https://example.com/watch';
const FIXTURE = (() => {
  const run = spawnSync('python', [path.join(REPO, '_main', 'history-retention-fixture.py')], {
    encoding: 'utf8',
    // THE CONSOLE GUARD: a console child of an agent paints a window on the
    // owner's screen without it (AGENTS.md, measured 2026-11-08).
    windowsHide: true,
  });
  if (run.error || run.status !== 0) {
    console.log(`FIXTURE FAIL rc=${run.status} error=${run.error ? run.error.message : 'none'}`);
    console.log(String(run.stdout || '').slice(0, 400));
    console.log(String(run.stderr || '').slice(-600));
    process.exit(2);
  }
  const parsed = JSON.parse(run.stdout);
  /* The JSON already carries every fact the arms need, so the temporary history
   * root (three tiny files under the temp dir) is removed HERE instead of being
   * left behind on every run -- a probe that litters is a probe that grows. */
  rmSync(parsed.root, { recursive: true, force: true });
  return parsed;
})();
/* The module source, for the negative arm: a mutant is SERVED to the page
 * through `page.route` instead of copying the 35 MB panel directory per mutant
 * -- measured working for a `file://` module load on this engine. */
const PANEL_JS = readFileSync(path.join(REPO, 'app', 'panel', 'panel.js'), 'utf8');

const rowVisible = (r) => Boolean(r) && r.display !== 'none' && r.visibility !== 'hidden'
  && Number(r.opacity) > 0 && r.width > 0 && r.height > 0
  && r.offsetParent && r.inViewport;

async function searchArm(rpage, query) {
  await rpage.evaluate(() => { window.__searchCalls.length = 0; });
  const shown = await rpage.evaluate(() => {
    const input = document.getElementById('history-search');
    if (!input) return false;
    const cs = getComputedStyle(input);
    return cs.display !== 'none' && cs.visibility !== 'hidden'
      && input.getBoundingClientRect().width > 0;
  });
  if (!shown) await rpage.click('#history-search-button');
  await rpage.fill('#history-search', query);
  await rpage.press('#history-search', 'Enter');
  await rpage.waitForFunction(() => {
    const note = document.getElementById('history-status');
    return Boolean(note && /match/.test(note.textContent || ''));
  }, null, { timeout: 10000 });
  return rpage.evaluate((q) => {
    const rows = [...document.querySelectorAll('#history-list .hist')];
    const row = rows.find((el) => (el.textContent || '').includes('RETENCAO-60D')) || null;
    const note = row ? row.querySelector('.hist__ctx') : null;
    return {
      query: q,
      calls: [...window.__searchCalls],
      count: rows.length,
      hasSixty: Boolean(row),
      hasTwoHundred: rows.some((el) => (el.textContent || '').includes('RETENCAO-200D')),
      ctxNote: note ? note.textContent : '',
      ctxMarks: note ? [...note.querySelectorAll('mark')].map((m) => m.textContent) : [],
      status: (document.getElementById('history-status') || {}).textContent || '',
    };
  }, query);
}

async function retentionArms(mutantJs) {
  const rctx = await browser.newContext({ viewport: { width: 380, height: 900 } });
  await rctx.addInitScript(FAKE_BRIDGE, { rows: FIXTURE.tail, hits: FIXTURE.searches });
  const rpage = await rctx.newPage();
  const errs = [];
  rpage.on('pageerror', (e) => errs.push(String(e)));
  if (mutantJs) {
    await rpage.route('**/panel.js', (route) => route.fulfill({
      contentType: 'text/javascript', body: mutantJs,
    }));
  }
  await rpage.goto(PANEL, { waitUntil: 'load' });
  await rpage.waitForFunction(
    () => document.querySelectorAll('#history-list .hist').length >= 1, null, { timeout: 15000 });
  const feed = await rpage.evaluate(() => {
    const rows = [...document.querySelectorAll('#history-list .hist')];
    const find = (needle) => rows.find((el) => (el.textContent || '').includes(needle)) || null;
    const info = (el) => {
      if (!el) return null;
      const cs = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const text = el.querySelector('.hist__text');
      const chip = el.querySelector('.hist__time');
      return {
        text: (el.textContent || '').trim(),
        context: el.dataset.context || '',
        title: el.title || '',
        textTitle: text ? (text.title || '') : '',
        chip: chip ? chip.textContent : null,
        chipTitle: chip ? (chip.title || '') : '',
        display: cs.display, visibility: cs.visibility, opacity: cs.opacity,
        width: Math.round(rect.width), height: Math.round(rect.height),
        inViewport: rect.width > 0 && rect.height > 0 && rect.top >= -1
          && rect.bottom <= window.innerHeight + 1,
        offsetParent: el.offsetParent !== null,
      };
    };
    return {
      count: rows.length,
      texts: rows.map((el) => (el.textContent || '').trim()),
      sixty: info(find('RETENCAO-60D')),
      near: info(find('RETENCAO-PERTO')),
      twoHundred: info(find('RETENCAO-200D')),
    };
  });
  const one = await searchArm(rpage, FIXTURE.queries.one);
  const leak = await searchArm(rpage, FIXTURE.queries.both);
  await rctx.close();
  const arms = {
    feedCount: feed.count === FIXTURE.expected.feedRows,
    feedSixty: rowVisible(feed.sixty),
    //: The row one day inside the SHELL's window (its age comes from the
    //: fixture's `retention_h`, not from a second literal here). This is what
    //: forbids a panel window narrower than the store's -- the 48 h defect.
    feedNear: rowVisible(feed.near),
    feedNoLeak: !feed.twoHundred,
    ctxPaint: Boolean(feed.sixty) && feed.sixty.context === EXPECTED_CTX
      && feed.sixty.title === EXPECTED_CTX && feed.sixty.textTitle === EXPECTED_CTX,
    searchCtx: one.calls.length === 1 && one.calls[0] === FIXTURE.queries.one
      && one.count === 1 && one.hasSixty && one.ctxNote.includes('main.py')
      && one.ctxMarks.includes('main.py'),
    searchNoLeak: leak.count === 0 && !leak.hasTwoHundred,
    // O CHIP CONTINUA SO' A HORA (ordem de 2026-11-06) e o DIA viaja no `title`.
    chipIsHourOnly: Boolean(feed.sixty) && /^\d{2}:\d{2}:\d{2}$/.test(feed.sixty.chip || ''),
    dayInTitle: Boolean(feed.sixty)
      && /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(feed.sixty.chipTitle || ''),
  };
  return { arms, feed, one, leak, errs };
}

const retention = await retentionArms(null);
const ra = retention.arms;
console.log(`RETENTION DOM: feed rows=${retention.feed.count} (want ${FIXTURE.expected.feedRows})`
  + ` 60-day=${ra.feedSixty ? 'visible' : 'MISSING/HIDDEN'}`
  + ` near(${FIXTURE.expected.nearDays}d)=${ra.feedNear ? 'visible' : 'MISSING/HIDDEN'}`
  + ` 200-day=${retention.feed.twoHundred ? 'LEAKED' : 'excluded'}`
  + ` context=${JSON.stringify(retention.feed.sixty ? retention.feed.sixty.context : null)}`);
console.log(`  search "${FIXTURE.queries.one}": calls=${JSON.stringify(retention.one.calls)}`
  + ` rows=${retention.one.count} ctxNote=${JSON.stringify(retention.one.ctxNote)}`
  + ` marks=${JSON.stringify(retention.one.ctxMarks)}`);
console.log(`  search "${FIXTURE.queries.both}": rows=${retention.leak.count}`
  + ` 200-day=${retention.leak.hasTwoHundred ? 'LEAKED' : 'excluded'}`
  + ` note=${JSON.stringify(retention.leak.status)}`);
console.log(`RETENTION ARMS ${Object.entries(ra).map(([k, v]) => `${k}=${v ? 'GREEN' : 'RED'}`).join(' ')}`);
if (Object.values(ra).some((v) => !v)) {
  console.log('RETENTION FAIL -- the panel window, the context paint and the search disagree');
}

/* THE NEGATIVE ARM OF THE RETENTION ARMS: one SURGICAL mutation of the shipped
 * `panel.js` per arm, served to the page through `page.route`, and each mutant
 * must turn its OWN arm RED. A control that copies "the previous panel.js" rots
 * the day the cure is committed; a control that mutates nothing proves nothing,
 * so an anchor that is not in the source is IMPOSSIBLE (rc=2), never a pass.
 * Convention: this mode exits 1 when it CATCHES. */
const MUTANTS = [
  { label: 'HISTORY_RETENTION_H 4320 -> 48',
    from: 'const HISTORY_RETENTION_H = 4320;',
    to: 'const HISTORY_RETENTION_H = 48;',
    red: ['feedCount', 'feedSixty', 'feedNear', 'ctxPaint'] },
  { label: 'HISTORY_RETENTION_H 4320 -> 2160 (90 days)',
    from: 'const HISTORY_RETENTION_H = 4320;',
    to: 'const HISTORY_RETENTION_H = 2160;',
    red: ['feedNear'] },
  { label: 'context paint removed',
    from: '    li.dataset.context = ctxSummary;',
    to: '',
    red: ['ctxPaint'] },
  { label: 'context note removed',
    from: '    if (hitQuery && !matches(entry.text, hitQuery) && matches(ctxSummary, hitQuery)) {',
    to: '    if (false) {',
    red: ['searchCtx'] },
  { label: 'window predicate admits everything',
    from: '  return !Number.isFinite(at) || at >= Date.now() - HISTORY_RETENTION_H * 3600 * 1000;',
    to: '  return true;',
    red: ['feedNoLeak'] },
  { label: 'search window removed',
    from: '  const list = (Array.isArray(hits) ? hits : []).filter(withinHistoryWindow);',
    to: '  const list = Array.isArray(hits) ? hits : [];',
    red: ['searchNoLeak'] },
];
let MUTANT_RESULTS = null;
if (NEG_ARM) {
  MUTANT_RESULTS = [];
  for (const m of MUTANTS) {
    if (!PANEL_JS.includes(m.from)) {
      console.log(`NEG-ARM: IMPOSSIBLE -- ${m.label}: the anchor is not in panel.js`);
      process.exit(2);
    }
    const run = await retentionArms(PANEL_JS.replace(m.from, m.to));
    const missed = m.red.filter((name) => run.arms[name]);
    MUTANT_RESULTS.push({ label: m.label, red: m.red, missed });
    console.log(`  mutant ${m.label}: ${m.red.map((n) => `${n}=${run.arms[n] ? 'STILL-GREEN' : 'RED'}`).join(' ')}`);
  }
}

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
const dimLine = [];
for (const t of report) {
  const r = t.rows.find((x) => x.body != null && x.body < 4.5);
  if (r) dimLine.push({ theme: t.theme, body: r.body, textColor: r.textColor });
}
const families = new Map();
for (const t of report) {
  const r = t.rows[0];
  if (!r) continue;
  const face = String(r.family || '').split(',')[0].replace(/["']/g, '').trim()
    + ' ' + r.fontSize;
  families.set(face, (families.get(face) || 0) + 1);
}
const stamped = report.reduce((n, t) => n + (t.rows.some((r) => r.stamp != null) ? 1 : 0), 0);
console.log(`STAMP UNREADABLE (<3:1 over its own background) in ${unreadable.length} of ${stamped} theme(s)`);
for (const r of unreadable) console.log(`  ${r.theme}: stamp=${r.stamp}:1 body=${r.body}:1 (${r.timeColor} / opacity ${r.timeOpacity})`);
console.log(`STAMP LOUDER THAN TEXT in ${louder.length} theme(s)`);
for (const r of louder) console.log(`  ${r.theme}: stamp=${r.stamp}:1 body=${r.body}:1`);
for (const t of clamped) console.log(`  ${t.theme}: clamp=${t.rows.find((r) => r.lineClamp !== 'none').lineClamp}`);
console.log(`LINE UNREADABLE (<4.5:1 over its own background) in ${dimLine.length} of ${report.length} theme(s)`);
for (const r of dimLine) console.log(`  ${r.theme}: body=${r.body}:1 (${r.textColor})`);
console.log(`ROW FACE: ${families.size} distinct (family + size) across ${report.length} theme(s)`);
for (const [face, n] of [...families.entries()].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${String(n).padStart(2)} theme(s): ${face}`);
}
console.log(`NOT LEFT-ALIGNED rows in ${centered.length} theme(s)`);
for (const t of centered) console.log(`  ${t.theme}: textAlign=${t.rows.find((r) => r.textAlign !== 'start' && r.textAlign !== 'left').textAlign}`);
if (errors.length) {
  console.log(`PAGE ERRORS: ${errors.length}`);
  for (const e of errors.slice(0, 5)) console.log('  ' + e);
}
if (JSON_OUT) {
  writeFileSync(JSON_OUT, JSON.stringify({
    themes: report,
    retention: { arms: ra, feed: retention.feed, one: retention.one, leak: retention.leak },
    fixture: { queries: FIXTURE.queries, expected: FIXTURE.expected, retention_h: FIXTURE.retention_h },
    mutants: MUTANT_RESULTS,
    errors,
  }, null, 2));
}
if (NEG_ARM) {
  const identityCaught = families.size < 2;
  const caught = (MUTANT_RESULTS || []).filter((r) => r.missed.length === 0).length;
  const total = (MUTANT_RESULTS || []).length;
  const all = identityCaught && caught === total && total > 0;
  console.log(`NEG-ARM: ${all ? 'PASS' : 'FAIL'} -- identity ${identityCaught ? 'caught' : 'NOT caught'}`
    + ` (${families.size} face(s), the positive measures 28); ${caught}/${total} retention mutant(s) caught`);
  for (const r of MUTANT_RESULTS || []) {
    if (r.missed.length) console.log(`  NOT CAUGHT: ${r.label} (still green: ${r.missed.join(', ')})`);
  }
  process.exit(all ? 1 : 0);
}
process.exit(bad.length || dimLine.length || families.size < 20 || errors.length
  || Object.values(ra).some((v) => !v) ? 1 : 0);
