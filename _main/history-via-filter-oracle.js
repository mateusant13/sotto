#!/usr/bin/env node
'use strict';

/**
 * HISTORY-VIA-FILTER ORACLE -- the two source buttons on the transcript, as
 * numbers instead of a screenshot.
 *
 * THE OWNER'S ORDER (2026-11-09, verbatim): *"dois filtros no historico: icone PC
 * e icone YouTube, ambos on/off, nunca os dois off"*. Two sources, two toggles,
 * and one rule the UI has to enforce BY ITSELF: the feed can never be filtered
 * into nothing.
 *
 * WHAT IS JUDGED, AND HOW. The functions are the REAL ones from `panel.js`
 * (`viaOf`, `viaVisible`, `toggleViaFilter`, `paintViaFilters`,
 * `wireViaFilters`), lifted out of the shipped file by SLICE and executed in a
 * `vm` context with a fake `document` carrying the two buttons. Nothing is
 * re-implemented here: a copy of the rule would pass while the shipped one broke.
 *
 *   A1  a `pc` line and a `youtube` line are BOTH visible with both filters on
 *   A2  `external` (a player that is not the YouTube tab) belongs to the VIDEO
 *       button -- the two buttons are "from this machine" / "from a video", and a
 *       third origin must not vanish from both
 *   A3  a line with NO `via` (written before the contract) reads as `pc`
 *   A4  turning `pc` off hides pc lines and keeps the video lines
 *   A5  NEVER BOTH OFF: turning the last one off turns the other back on
 *   A6  the buttons are PAINTED from the state (`aria-pressed` + `is-off`), not
 *       from the DOM
 *   A7  the CLICK is wired: one click on `#history-filter-pc` turns it off
 *   A8  a filtered feed is REBUILT (the whole predicate repaints), not patched
 *
 * Usage:
 *   node _main/history-via-filter-oracle.js            the arms + the VERDICT
 *   node _main/history-via-filter-oracle.js --neg-arm  the mutants, EXECUTED
 *
 * `SOTTO_PANEL_DIR` points the whole oracle at another copy of `app/panel`, which
 * is how the negative arm runs a mutant.
 *
 * Exit codes: 0 every arm passed | 1 an arm failed (or, in `--neg-arm`, a mutant
 * was NOT caught) | 2 setup error. No window, no browser, no audio, no network.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const NEG = process.argv.includes('--neg-arm');

function panelDir() {
  return process.env.SOTTO_PANEL_DIR
    ? path.resolve(process.env.SOTTO_PANEL_DIR)
    : path.join(REPO, 'app', 'panel');
}

/* ─────────────────────────── the real source, sliced ────────────────────── */

/** The body of ONE top-level `function name(...) { ... }`, by brace matching. */
function sliceFunction(src, name) {
  const head = `function ${name}(`;
  const start = src.indexOf(head);
  if (start < 0) throw new Error(`FATAL: function ${name} is not in panel.js`);
  let i = src.indexOf('{', start);
  let depth = 0;
  for (; i < src.length; i += 1) {
    if (src[i] === '{') depth += 1;
    else if (src[i] === '}') {
      depth -= 1;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error(`FATAL: unbalanced braces in function ${name} of panel.js`);
}

/** The `const NAME = ...;` declaration, by statement terminator. */
function sliceConst(src, name) {
  const head = `const ${name} = `;
  const start = src.indexOf(head);
  if (start < 0) throw new Error(`FATAL: ${head.trim()} is not in panel.js`);
  const end = src.indexOf('\n', start);
  return src.slice(start, end < 0 ? src.length : end);
}

/** THE FILTER ONLY: the two constants and the six functions, NOT a byte range. */
const FILTER_FUNCS = ['viaOf', 'viaVisible', 'paintViaFilters',
                      'repaintFeedForFilter', 'toggleViaFilter', 'wireViaFilters'];

function filterSource() {
  const file = path.join(panelDir(), 'panel.js');
  const src = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
  const parts = [sliceConst(src, 'viaFilter'), sliceConst(src, 'VIA_KEYS')];
  for (const name of FILTER_FUNCS) parts.push(sliceFunction(src, name));
  // A `const` in a script is LEXICAL: it never lands on the context object, so
  // the arms could not read the state at all. One bridge line, added by the
  // ORACLE (never by the shipped file), exposes the SAME objects the shipped
  // functions mutate -- a copy would measure a stale value.
  parts.push('globalThis.__viaFilter = viaFilter; globalThis.__VIA_KEYS = VIA_KEYS;');
  return parts.join('\n');
}

/* ───────────────────────────── the fake page ────────────────────────────── */

function fakeButton() {
  const attrs = {};
  return {
    attrs,
    classes: new Set(),
    listeners: [],
    setAttribute(name, value) { attrs[name] = String(value); },
    getAttribute(name) { return name in attrs ? attrs[name] : null; },
    classList: null,
    addEventListener(kind, fn) { this.listeners.push([kind, fn]); },
    click() { for (const [kind, fn] of this.listeners) if (kind === 'click') fn(); },
  };
}

function makeButton() {
  const b = fakeButton();
  b.classList = {
    toggle(name, on) {
      if (on) b.classes.add(name); else b.classes.delete(name);
    },
  };
  return b;
}

/**
 * Run the real block against a fake document. Returns the namespace so an arm
 * can call the shipped functions directly.
 */
function load(repaintLog) {
  const buttons = {
    'history-filter-pc': makeButton(),
    'history-filter-youtube': makeButton(),
  };
  const document = {
    getElementById(id) { return buttons[id] || null; },
  };
  // The two module-level values the block reads when it repaints: the feed view
  // and the search view are the same slot, so a filter change must repaint
  // whichever is showing.
  const sandbox = {
    document,
    searchQuery: '',
    searchHits: [],
    renderFeed() { repaintLog.push('feed'); },
    renderSearchResults() { repaintLog.push('search'); },
    console,
  };
  // THE DESIGN'S OWN FROZEN LIST IS THE SECOND CONSUMER (owner, 2026-11-09: the
  // design list obeys the same two buttons). A spy, so the forwarding is judged
  // as an EFFECT rather than as a line of text.
  sandbox.SottoSkin = {
    calls: [],
    filterVia(state) { this.calls.push(state); },
  };
  // In the page `window` IS the global; a plain object here would make `SottoSkin`
  // (read bare in `paintViaFilters`) a `ReferenceError` in the sandbox only.
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(filterSource(), sandbox, { filename: 'panel.js#via-filter' });
  return { sandbox, buttons };
}

/* ─────────────────────────────── the arms ───────────────────────────────── */

/** The live filter state of one loaded sandbox (same object the functions use). */
function state(sandbox) {
  return sandbox.__viaFilter;
}

function arms() {
  const checks = [];
  const add = (name, ok, detail) => checks.push({ name, ok: !!ok, detail });

  // A1/A2/A3 -- the predicate over one entry, both filters on.
  {
    const log = [];
    const { sandbox } = load(log);
    const pc = { via: 'pc', text: 'a' };
    const yt = { via: 'youtube', text: 'b' };
    const ext = { via: 'external', text: 'c' };
    const legacy = { text: 'd' };
    add('a1_pc_reads_as_pc', sandbox.viaOf(pc) === 'pc', sandbox.viaOf(pc));
    add('a1_youtube_reads_as_youtube', sandbox.viaOf(yt) === 'youtube', sandbox.viaOf(yt));
    add('a2_external_belongs_to_the_video_button',
        sandbox.viaOf(ext) === 'youtube', sandbox.viaOf(ext));
    add('a3_legacy_line_reads_as_pc',
        sandbox.viaOf(legacy) === 'pc' && sandbox.viaOf(null) === 'pc',
        `${sandbox.viaOf(legacy)}/${sandbox.viaOf(null)}`);
    add('a1_both_visible_when_both_on',
        sandbox.viaVisible(pc) && sandbox.viaVisible(yt) && sandbox.viaVisible(ext),
        `pc=${sandbox.viaVisible(pc)} yt=${sandbox.viaVisible(yt)} ext=${sandbox.viaVisible(ext)}`);
  }

  // A4/A5 -- the toggles, and the never-both-off rule.
  {
    const log = [];
    const { sandbox, buttons } = load(log);
    sandbox.toggleViaFilter('pc');           // pc OFF
    add('a4_pc_off_hides_pc_lines',
        sandbox.viaVisible({ via: 'pc' }) === false,
        `pcOn=${state(sandbox).pc}`);
    add('a4_pc_off_keeps_video_lines',
        sandbox.viaVisible({ via: 'youtube' }) === true,
        `ytOn=${state(sandbox).youtube}`);
    sandbox.toggleViaFilter('youtube');      // the LAST one off
    add('a5_never_both_off',
        state(sandbox).pc !== false || state(sandbox).youtube !== false,
        `pc=${state(sandbox).pc} yt=${state(sandbox).youtube}`);
    add('a5_the_other_one_came_back',
        state(sandbox).pc === true && state(sandbox).youtube === false,
        `pc=${state(sandbox).pc} yt=${state(sandbox).youtube}`);
    // A6 -- painted from the state.
    add('a6_buttons_painted_from_state',
        buttons['history-filter-pc'].attrs['aria-pressed'] === 'true'
        && buttons['history-filter-youtube'].attrs['aria-pressed'] === 'false'
        && buttons['history-filter-youtube'].classes.has('is-off'),
        `pc=${buttons['history-filter-pc'].attrs['aria-pressed']} `
        + `yt=${buttons['history-filter-youtube'].attrs['aria-pressed']}`);
  }

  // A7 -- the click is wired to the shipped toggle.
  {
    const log = [];
    const { sandbox, buttons } = load(log);
    sandbox.wireViaFilters();
    const before = state(sandbox).pc;
    buttons['history-filter-pc'].click();
    add('a7_click_toggles_the_source',
        state(sandbox).pc !== before,
        `before=${before} after=${state(sandbox).pc}`);
  }

  // A9 -- the DESIGN list (the frozen gallery) obeys the same buttons.
  {
    const log = [];
    const { sandbox } = load(log);
    sandbox.toggleViaFilter('pc');
    const last = sandbox.SottoSkin.calls[sandbox.SottoSkin.calls.length - 1];
    add('a9_design_list_obeys_the_buttons',
        !!last && last.pc === false && last.youtube === true,
        JSON.stringify(last || null));
  }

  // A8 -- A TOGGLE REPAINTS: the filtered feed is rebuilt from the whole
  // predicate, and the SEARCH view (the same slot) is rebuilt too. Measured on
  // the TOGGLE path, not by calling the repaint directly -- a mutant that drops
  // the call from `toggleViaFilter` would otherwise pass, which is exactly what
  // the first draft of this arm did.
  {
    const log = [];
    const { sandbox } = load(log);
    log.length = 0;
    sandbox.toggleViaFilter('pc');       // pc OFF -> the filtered view
    add('a8_filter_repaints_the_feed',
        log.length === 1 && log[0] === 'feed', JSON.stringify(log));
    const log2 = [];
    const second = load(log2);
    second.sandbox.searchQuery = 'x';
    log2.length = 0;
    second.sandbox.toggleViaFilter('pc');
    add('a8_filter_repaints_the_search_view_too',
        log2.length === 1 && log2[0] === 'search', JSON.stringify(log2));
  }

  // A10 -- NEVER BOTH OFF, SEEN AT EVERY STEP. The first draft only looked at
  // the state AFTER a pair of toggles, and a mutant that turned both off on the
  // FIRST one then restored one on the second walked straight past it. The
  // invariant is about every intermediate state, so it is measured there.
  {
    const log = [];
    const { sandbox } = load(log);
    const seen = [];
    let bothOff = false;
    for (const via of ['pc', 'youtube', 'pc', 'youtube', 'youtube', 'pc']) {
      sandbox.toggleViaFilter(via);
      const st = state(sandbox);
      seen.push(`${via}:${st.pc === false ? '0' : '1'}${st.youtube === false ? '0' : '1'}`);
      if (st.pc === false && st.youtube === false) bothOff = true;
    }
    add('a10_never_both_off_at_any_step', !bothOff, seen.join(' '));
  }

  return checks;
}

/* ────────────────────────────── the mutants ─────────────────────────────── */

const MUTANTS = [
  {
    name: 'm1-external-read-as-pc',
    find: "  if (value === 'youtube' || value === 'external') return 'youtube';",
    replace: "  if (value === 'youtube') return 'youtube';",
    caught_by: 'a2_external_belongs_to_the_video_button',
  },
  {
    name: 'm2-both-off-allowed',
    find: '    if (viaFilter[other] === false) viaFilter[other] = true;',
    replace: '    viaFilter[other] = false;',
    caught_by: 'a10_never_both_off_at_any_step',
  },
  {
    name: 'm3-nothing-painted',
    find: "    button.setAttribute('aria-pressed', on ? 'true' : 'false');",
    replace: "    button.setAttribute('aria-pressed', 'true');",
    caught_by: 'a6_buttons_painted_from_state',
  },
  {
    name: 'm4-click-not-wired',
    find: "    button.addEventListener('click', () => toggleViaFilter(via));",
    replace: "    void button;",
    caught_by: 'a7_click_toggles_the_source',
  },
  {
    name: 'm5-filter-never-repaints',
    find: '  paintViaFilters();\n  repaintFeedForFilter();',
    replace: '  paintViaFilters();',
    caught_by: 'a8_filter_repaints_the_feed',
  },
];

function runMutants() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sotto-via-mut-'));
  const copy = path.join(dir, 'panel');
  fs.mkdirSync(copy);
  fs.copyFileSync(path.join(panelDir(), 'panel.js'), path.join(copy, 'panel.js'));
  // LF ON PURPOSE: the shipped file is CRLF, and a multi-line anchor written
  // with `\n` never matches CRLF text -- the mutant would be byte-identical to
  // the source and the arm would pass vacuously (the `history-write-oracle`
  // paid for this lesson already).
  const original = fs.readFileSync(path.join(copy, 'panel.js'), 'utf8').replace(/\r\n/g, '\n');
  fs.writeFileSync(path.join(copy, 'panel.js'), original, 'utf8');
  const results = [];
  for (const m of MUTANTS) {
    if (!original.includes(m.find)) {
      results.push({ name: m.name, ok: false, detail: 'mutant anchor not found in panel.js' });
      continue;
    }
    const mutated = original.replace(m.find, m.replace);
    if (mutated === original) {
      results.push({ name: m.name, ok: false, detail: 'mutation did not change the file' });
      continue;
    }
    fs.writeFileSync(path.join(copy, 'panel.js'), mutated, 'utf8');
    process.env.SOTTO_PANEL_DIR = copy;
    let caught = false;
    let detail = '';
    try {
      const got = arms();
      const failed = got.filter((c) => !c.ok).map((c) => c.name);
      caught = failed.includes(m.caught_by);
      detail = `failed=${failed.length ? failed.join(',') : '(none)'}`;
    } catch (err) {
      caught = true;
      detail = `threw: ${err && err.message}`;
    }
    results.push({ name: m.name, ok: caught, detail });
  }
  fs.writeFileSync(path.join(copy, 'panel.js'), original, 'utf8');
  delete process.env.SOTTO_PANEL_DIR;
  return results;
}

/* ──────────────────────────────── main ──────────────────────────────────── */

function main() {
  if (NEG) {
    const results = runMutants();
    let bad = 0;
    for (const r of results) {
      console.log(`${r.ok ? 'CAUGHT' : 'MISSED'} ${r.name} ${r.detail}`);
      if (!r.ok) bad += 1;
    }
    const ok = bad === 0;
    console.log(`NEG-ARM: ${ok ? 'PASS' : 'FAIL'} -- ${results.length - bad}/${results.length} mutants caught`);
    return ok ? 1 : 0;
  }
  const checks = arms();
  let bad = 0;
  for (const c of checks) {
    console.log(`ARM ${c.ok ? 'PASS' : 'FAIL'} ${c.name} ${c.detail}`);
    if (!c.ok) bad += 1;
  }
  console.log(`CHECK arms=${checks.length} failed=${bad}`);
  console.log(`VERDICT: ${bad === 0 ? 'PASS' : 'FAIL'}`);
  return bad === 0 ? 0 : 1;
}

try {
  process.exitCode = main();
} catch (err) {
  console.error(`SETUP FAILED ${err && err.stack ? err.stack : err}`);
  process.exitCode = 2;
}
