/* three-overlays-oracle.js -- the S3 gate: the owner's THREE overlays.
 *
 * THE OWNER'S ORDER, verbatim (2026-10-12 16:33):
 *   'e pra existir 3 overlays. primeiro, o painel de baixo. nele eu ativo o
 *   segundo overlay, q e a legenda independente. ela mostra na minha tela, sem fundo,
 *   sem nada, extremamente clean, e apenas algo pra estilizar ela ou dar corpo.
 *   tipo uma barra a esquerda dela, onde ela se apoia... o terceiro painel, e o da
 *   direita. onde deve ter todos os botoes. o painel de baixo, deve conter apenas o
 *   bare minimum. e e so no painel da direita que aparece historico de qualquer
 *   coisa. faca tudo.'
 *
 * AND THE BUG THAT CAME WITH IT, verbatim:
 *   'e o alt c ta bugado. ta uma cor solida, uma div inteira. no meio dela, tinha
 *   o painel de baixo. cliquei num botao e ele sumiu e agora ta so a cor solida de
 *   volta, inteira.'
 *
 * WHAT THIS GATES, one check per claim:
 *   A. THREE SURFACES exist: the bottom strip, the floated caption, the right panel.
 *   B. THE NO-BACKGROUND INVARIANT: no rule paints a background or a box on
 *      .caption-float itself (the owner: 'sem fundo, sem nada').
 *   C. HISTORY ONLY IN THE RIGHT PANEL: .history is display:none on the strip and
 *      reachable on the panel, and no history node lives in the strip markup.
 *   D. BUTTON PLACEMENT: the strip carries the bare minimum; every button lives on
 *      the right panel.
 *   E. THE BUG IS CLOSED: nothing can hide the slab any more, and the strip bar
 *      FILLS its window (the inverse of the solid-colour report).
 *   F. THE CAPTION DESIGN follows the zips (I:/cc-tmp/zip1): the 4px breathing
 *      bar, the OUVINDO... empty state, the font dial, the height adaptation.
 *
 * WHY A NEW ORACLE: _main/strip-float-oracle.js (the S2 gate, written 2026-10-12
 * 17:02) pins the strip rebuild that PRODUCED the owner's report -- its S3 asserts
 * width:max-content on the strip panel and its S5 asserts
 * body[data-surface='strip'] { background: transparent }. Those two rules ARE the
 * bug: the shell's window is 1040x100 (measured, _main/webview-run.log line 114720:
 * 'STRIP_HEIGHT from=148 to=40 source=css css_value=40' followed by
 * 'window=1040x100@(440,920)'), and the shell paints the unpainted window with an
 * OPAQUE #0B0F14 (sotto_webview.py:3926-3931), so a centred max-content pill on a
 * transparent body IS the owner's 'uma cor solida, uma div inteira. no meio dela,
 * tinha o painel de baixo'. This oracle supersedes those two checks. The S2 oracle
 * is left untouched (another lane's file) and is expected to report S3/S5 RED until
 * the Lead retires or re-baselines it; recorded in
 * _main/receipt-20261012-three-overlays.md.
 *
 * --neg-arm: the panel files copied to a scratch dir with ONE behaviour broken
 * each, and the SAME checks re-run against the copies. Every mutant must go RED
 * or the oracle cannot say no. RE-BASELINED 2026-10-13 for the owner's ruling that
 * the LIVE button IS the caption control; nine mutants, one per invariant.
 */
'use strict';

const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

const ROOT = path.resolve(__dirname, "..");
const PANEL = path.join(ROOT, "app", "panel");
const NEG = process.argv.includes("--neg-arm");

const read = (p) => fs.readFileSync(p, "utf8");

/* A real rule parser: strips comments, then walks the bytes tracking depth, so a
   selector LIST (a, b { }) and a nested @media block are both handled. Returns
   [{selector, members, decls, line}] where members is the comma-split list. */
function parse(css) {
  const src = css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
  const out = [];
  let i = 0, line = 1, buf = '', depth = 0, sel = null;
  const flush = () => {
    if (sel == null) return;
    const decls = {};
    for (const d of buf.split(';')) {
      const c = d.indexOf(':');
      if (c > 0) decls[d.slice(0, c).trim().toLowerCase()] = d.slice(c + 1).trim();
    }
    out.push({ selector: sel.trim(), members: sel.split(',').map((s) => s.trim()), decls: decls, line: line });
    sel = null; buf = '';
  };
  while (i < src.length) {
    const ch = src[i];
    if (ch === '\n') { line++; i++; continue; }
    if (ch === '{') { depth++; if (depth === 1) { sel = buf; buf = ''; } i++; continue; }
    if (ch === '}') { depth--; if (depth === 0) flush(); i++; continue; }
    if (depth === 1) buf += ch; else if (depth === 0 && ch !== ' ') buf += ch;
    i++;
  }
  return out;
}

/* Does ANY rule whose selector list contains MEMBER (exact) declare PROP? */
function declares(rules, member, prop) {
  const p = prop.toLowerCase();
  return rules.some((r) => r.members.indexOf(member) >= 0 && p in r.decls);
}

/* The declaration value for the FIRST rule that owns MEMBER + PROP. */
function valueOf(rules, member, prop) {
  const p = prop.toLowerCase();
  const r = rules.find((x) => x.members.indexOf(member) >= 0 && p in x.decls);
  return r ? r.decls[p] : null;
}

function checks(dir) {
  const html = read(path.join(dir, 'panel.html'));
  const css = read(path.join(dir, 'panel.css'));
  const js = read(path.join(dir, 'panel.js'));
  const float = read(path.join(dir, 'caption-float.js'));
  const rules = parse(css);
  const out = [];
  const add = (name, ok, detail) => out.push({ name: name, ok: !!ok, detail: String(detail == null ? '' : detail) });
  const has = (id) => html.indexOf('id="' + id + '"') >= 0;
  /* THE MARKUP, WITHOUT THE NOTES. panel.html documents the controls it REMOVED
     in HTML comments (panel.html:301-304, :725-728, :807-818), so a grep over the
     raw document finds the button the owner cut -- inside the sentence that says
     the button is gone. A gate that reads the note as the thing measures PROSE.
     The markup below is the document with its comments stripped, which is what
     the product's own note asks for (*"MEASURED: `id="strip-theme-button"` is
     absent from this document"*, panel.html:303). */
  const markup = html.replace(/<!--[\s\S]*?-->/g, '');
  /* THE CODE, WITHOUT ITS PROSE. panel.js explains in comments the constants it
     DELETED -- the name `FLOAT_HEIGHT` survives ONLY there (panel.js:65, :2693)
     -- so a check that reads the CODE reads the code, not the note about it. */
  const jsCode = js.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^[ \t]*\/\/.*$/gm, ' ');
  const stripRules = rules.filter((r) => r.members.some((m) => m.indexOf('[data-surface="strip"]') >= 0));
  const panelRules = rules.filter((r) => r.members.some((m) => m.indexOf('[data-surface="panel"]') >= 0));

  /* ---- A. THREE SURFACES ---------------------------------------------- */
  add('A1 the bottom surface exists (strip-scoped rules)',
    stripRules.length > 0, stripRules.length + ' rule(s)');
  add('A2 the right surface exists (panel-scoped rules)',
    panelRules.length > 0, panelRules.length + ' rule(s)');
  add('A3 the caption overlay is gated on data-float, not on the surface alone',
    valueOf(rules, '.caption-float', 'display') === 'none' &&
    /body\[data-surface="strip"\]\[data-float="on"\]\s+\.caption-float\s*\{\s*display:\s*block/.test(css),
    'display:none by default; block only on strip+float');
  add('A4 the strip OPEN button reaches the right panel',
    /function openFullPanel\(reason\)[\s\S]{0,220}?bridge\.setPanelSurface\('panel',\s*reason\)/.test(js) && has('strip-open-button'),
    "openFullPanel -> bridge.setPanelSurface('panel', reason)");
  /* RE-ANCHORED 2026-10-20 (lane caption). The old third clause demanded
     `setStripHeight(on ? FLOAT_HEIGHT : STRIP_HEIGHT)` -- the TWO-HEIGHT contract
     the product DELETED on 2026-10-17 (panel.js:62-85, verbatim: *"the constant
     that produced it is deleted instead of being re-tuned"*). There is ONE height
     now, `STRIP_HEIGHT = '40px'`, and `applyFloat` writes it unconditionally
     (panel.js:2734). The clause below reads the CODE with its comments
     stripped, so the note that explains the deletion cannot be mistaken for the
     deletion itself. */
  add('A5 the LIVE button is bound and the window height is THE ONE HEIGHT',
    /stripLiveButton\.addEventListener\(.click./.test(jsCode) &&
    /applyFloat\(liveEnabled\)/.test(jsCode) &&
    /const\s+STRIP_HEIGHT\s*=\s*'40px'/.test(jsCode) &&
    /setStripHeight\(STRIP_HEIGHT\)/.test(jsCode) &&
    !/FLOAT_HEIGHT/.test(jsCode),
    'live click -> applyLiveEnabled -> applyFloat -> setStripHeight(STRIP_HEIGHT); no FLOAT_HEIGHT');

  /* ---- B. THE NO-BACKGROUND INVARIANT --------------------------------- */
  /* The owner: 'ela mostra na minha tela, sem fundo, sem nada, extremamente
     clean'. Asserted on the HOST (.caption-float) and on its stage: no background,
     no border, no box-shadow, no backdrop-filter, no outline. */
  const boxProps = ['background', 'background-color', 'border', 'border-top', 'border-bottom',
    'border-left', 'border-right', 'box-shadow', 'backdrop-filter', 'outline'];
  const host = rules.filter((r) => r.members.indexOf('.caption-float') >= 0);
  const hostDirty = host.filter((r) => boxProps.some((p) => p in r.decls));
  add('B1 no rule paints a background or a box on .caption-float itself',
    host.length > 0 && hostDirty.length === 0,
    host.length ? hostDirty.map((r) => r.decls[Object.keys(r.decls).filter((k) => boxProps.indexOf(k) >= 0)[0]]).join('; ') : 'no .caption-float rule');
  const stage = rules.find((r) => r.members.indexOf('.caption-float__stage') >= 0);
  add('B2 the overlay stage has no background',
    !!stage && !('background' in stage.decls) && !('background-color' in stage.decls),
    stage ? Object.keys(stage.decls).join(',') : 'no .caption-float__stage rule');
  add('B3 the overlay is click-through (pointer-events:none)',
    valueOf(rules, '.caption-float', 'pointer-events') === 'none',
    String(valueOf(rules, '.caption-float', 'pointer-events')));
  add('B4 the overlay is display:none until data-float=on',
    valueOf(rules, '.caption-float', 'display') === 'none',
    String(valueOf(rules, '.caption-float', 'display')));
  add('B5 the zip 4px breathing bar exists (the overlay only body)',
    has('caption-float') && /class="caption-float__led"/.test(html) &&
    /@keyframes\s+caption-led-breathe/.test(css) && /caption-float__led\s*\{[^}]*animation:/.test(css),
    '.caption-float__led + @keyframes caption-led-breathe');
  /* The CODE, never a comment that mentions it: the mutant that deletes the toggle
     left the word 'is-empty' in the surrounding comment and a text-only check stayed
     green (measured: N7 GREEN on the first neg-arm run). */
  add('B6 the zip OUVINDO... empty state exists',
    /classList\.toggle\('is-empty',\s*empty\)/.test(float) && /textContent\s*=\s*'OUVINDO/.test(float),
    "line.classList.toggle('is-empty', empty) + textContent = 'OUVINDO...'");

  /* ---- C. HISTORY ONLY IN THE RIGHT PANEL ----------------------------- */
  /* The transcript container is the EXACT class .history -- not .history__label,
     which has its own paused-state rules on both surfaces. The rule that hides it
     on the strip is one member of a four-member selector list (panel.css), so the
     matcher looks for the class token anywhere in the compound, never for the
     member to BE the class. */
  const isHistoryClass = (m) => /\.history(?![\w-])/.test(m);
  const histStrip = stripRules.filter((r) => r.members.some(isHistoryClass));
  add('C1 .history is display:none on the strip',
    histStrip.some((r) => r.decls.display === 'none'),
    histStrip.map((r) => r.selector + ' { display:' + r.decls.display + ' }').join(' | ') || 'no strip .history rule');
  /* The member ITSELF must be panel-scoped: a four-member list can carry a strip
     member and a panel member in the same rule, so filtering the rule by 'any
     member is panel-scoped' would read the STRIP's hide as the PANEL's. */
  const histPanel = panelRules.filter((r) => r.members.some((m) => isHistoryClass(m) && m.indexOf('[data-surface="panel"]') >= 0));
  add('C2 .history is reachable on the right panel (no display:none)',
    histPanel.length === 0 || !histPanel.some((r) => r.decls.display === 'none'),
    histPanel.length ? histPanel.map((r) => r.selector + ' { display:' + (r.decls.display || 'default') + ' }').join(' | ') : 'no panel-scoped .history rule');
  const bar = html.match(/<section class="stripbar"[\s\S]*?<\/section>/);
  const barIds = bar ? Array.from(bar[0].matchAll(/id="([^"]+)"/g)).map((m) => m[1]) : [];
  add('C3 no history/transcript node lives in the strip markup',
    !barIds.some((id) => /history|transcript/i.test(id)),
    barIds.join(','));
  add('C4 the theme picker and tune dialog are panel-only',
    /body\[data-surface="strip"\] \.theme-picker,\s*body\[data-surface="strip"\] #tune-dialog \{\s*display:\s*none\s*!important/.test(css),
    'display:none !important on the strip surface');

  /* ---- D. BUTTON PLACEMENT -------------------------------------------- */
  /* RE-BASELINED 2026-10-12 (Lead). The owner ordered the theme pill and the two
     font dials OUT of the strip -- verbatim: *"a porra do painel, e pra ser
     minimo"* -- so the old list of EIGHT pinned a contract he had cancelled, and
     this gate went red the moment the work was done. The assertion is now BOTH
     halves, which is the stronger form: the five that stay, and the three that
     must be GONE. A gate that only checks presence cannot tell "minimal" from
     "everything is still there". */
  const BARE = ['strip-live-button', 'strip-open-button', 'strip-hide-button',
    'strip-pause-button'];
  const CUT = ['strip-theme-button', 'strip-font-smaller-button',
    'strip-font-larger-button', 'strip-float-button'];
  add('D1 the strip carries the bare-minimum button set',
    BARE.every((id) => barIds.indexOf(id) >= 0),
    BARE.filter((id) => barIds.indexOf(id) < 0).join(',') || 'all ' + BARE.length + ' present');
  add('D1b and the buttons the owner cut are GONE',
    CUT.every((id) => barIds.indexOf(id) < 0),
    CUT.filter((id) => barIds.indexOf(id) >= 0).join(',') || 'all ' + CUT.length + ' absent');
  add('D2 the strip carries NO transparency button and NO theme chevron',
    !has('strip-transparency-button') && barIds.indexOf('strip-theme-chevron') < 0,
    'transparency:' + has('strip-transparency-button') + ' chevron:' + (barIds.indexOf('strip-theme-chevron') >= 0));
  add('D3 the chevron is hidden by CSS on the strip (theme-switcher re-creates it)',
    /body\[data-surface="strip"\] #strip-theme-chevron \{\s*display:\s*none/.test(css),
    'display:none on the strip surface');
  /* D4, RE-BASELINED 2026-10-18 on the owner's verbatim *"1 botao de tamanho em vez
   de 2"*. It asserted the smaller/larger PAIR, which no longer exists: the dial is
   ONE cycling button per surface (`#font-scale-button` on the panel,
   `#strip-font-scale-button` on the strip). A gate left naming the old ids would go
   RED the moment the owner's order was carried out, and a RED gate nobody can act
   on is how gates get switched off. */
  add('D4 the right panel holds ONE font button, pause and hide',
    has('font-scale-button') && has('panel-pause-button') && has('hide-button'),
    'font-scale panel-pause hide');
  /* AND the pair must be GONE, not merely un-asserted: a check that stops mentioning
     an id is indistinguishable from a check that stopped noticing it. */
  add('D4b and the smaller/larger PAIR is gone from the document',
    !has('font-smaller-button') && !has('font-larger-button') &&
    !has('strip-font-smaller-button') && !has('strip-font-larger-button'),
    'pair ids: ' + ['font-smaller-button', 'font-larger-button',
      'strip-font-smaller-button', 'strip-font-larger-button']
      .filter((id) => has(id)).join(',') || 'all 4 absent');
  /* RE-BASELINED 2026-10-14 (lane B) on the owner's OWN new words, verbatim: *"tira o
     botao de transcript. ha um botao/gaveta do transcript no painel. remove o CONTROLO.
     se a gaveta tiver de ficar por detras, esconde-a mas tira o botao."* The check used
     to DEMAND `history-toggle` -- the very control he ordered out -- so it went red the
     moment the work was done, which is the same shape as the 2026-10-12 theme-pill
     re-baseline above. The assertion is now BOTH halves, the stronger form: the CONTROL
     is gone, and the DRAWER it used to open is still on the panel, still in the DOM and
     still CSS-collapsed behind the bar. A gate that only checks absence cannot tell
     "the button was removed" from "the whole transcript was deleted". Control: N11
     below puts the button back and this check must go RED. */
  add('D5 the transcript BUTTON is gone and the drawer stays behind, collapsed',
    !has('history-toggle') && has('history') &&
    /\.history--collapsed \.history__body \{\s*display:\s*none/.test(css),
    'no history-toggle; #history present; .history__body collapsed');
  add('D5b the drawer keeps its own tools on the panel (search and reveal)',
    has('search-button') && has('reveal-button'),
    'search-button reveal-button');
  /* RE-BASELINED 2026-10-12 (Lead), same reason as D1: the owner cut the strip's
     theme control and the picker is now reached from the RIGHT panel only. The
     old form required the very button he removed.
     RE-ANCHORED 2026-10-20 (lane caption): the clause grepped the RAW panel.html
     for `id="strip-theme-button"`, and the ONLY occurrences of that string in the
     document are inside the COMMENTS that document the removal (panel.html:301-304,
     :725-728, :807-818). The gate was reading the NOTE as if it were the BUTTON --
     prose, not markup. The clause below reads the MARKUP (the document with its
     comments stripped). The control is unchanged: N8 below puts the button back
     in the markup and this check must go RED. */
  add('D6 the strip has NO theme button and the picker is panel-only',
    !/id="strip-theme-button"/.test(markup) && /body\[data-surface="strip"\] \.theme-picker/.test(css),
    'no id in the MARKUP + picker hidden on strip');

  /* ---- E. THE BUG IS CLOSED ------------------------------------------- */
  const trap = rules.filter((r) => r.members.some((m) => m.indexOf('[data-transparency="on"]') >= 0) && r.decls.display === 'none');
  add('E1 nothing hides the slab on data-transparency=on any more',
    trap.length === 0,
    trap.map((r) => r.selector).join(' | ') || 'no display:none under [data-transparency=on]');
  add('E2 the transparency button is gone from the markup and the dom table',
    !has('strip-transparency-button') && !/stripTransparencyButton\s*:\s*document\.getElementById/.test(js),
    'no id, no dom entry');
  add('E3 applyTransparency has no UI caller',
    !/stripTransparencyButton\.addEventListener/.test(js),
    'no addEventListener on a transparency button');
  const pill = /body\[data-surface="strip"\] \.panel \{[^{}]*width:\s*max-content/.test(css);
  const transparentBody = /body\[data-surface="strip"\] \{[^{}]*background:\s*transparent/.test(css);
  add('E4 the strip bar FILLS its window (no max-content pill, no transparent body)',
    !pill && !transparentBody, 'max-content:' + pill + ' transparent-body:' + transparentBody);
  add('E5 the strip panel paints its own surface',
    /body\[data-surface="strip"\] \.panel \{[^}]*background:/.test(css), 'background on the strip .panel');

  /* ---- F. THE CAPTION DESIGN (the zips are the authority) -------------- */
  add('F1 the stage is the zip flex row: bar + text column',
    /\.caption-float__stage \{[^}]*display:\s*flex/.test(css) && /class="caption-float__col"/.test(html),
    'display:flex + .caption-float__col');
  add('F2 the live line moves with the owner font dial',
    /\.caption-float__line \{[^}]*font-size:[^}]*var\(--caption-scale\)/.test(css),
    'font-size: calc(clamp(...) * var(--caption-scale))');
  add('F3 the overlay adapts to a short window (the shell hands out 100px today)',
    /@media \(max-height:\s*139px\)[\s\S]*?caption-float__prev/.test(css),
    '@media (max-height: 139px) hides the non-caption chrome');
  /* REBASED 2026-10-15. The contract MOVED, and it moved because the owner asked: verbatim
   * *"essa legenda ao vivo deveria aparecer no MEIO EM BAIXO da minha tela"*, and from his
   * original brief [860]: *"the live subtitles in the BOTTOM AND MIDDLE of the screen"*.
   * The caption used to be `top: 34px` -- stretched from under the bar to the bottom -- and
   * it is now `top: auto` with `bottom: 0`, which is what RESTS it on the bottom edge.
   *
   * THE OLD REGEX ALSO HAD A SECOND, QUIETER DEFECT: `\{\s*top:` required `top:` to be the
   * FIRST thing inside the block, so a COMMENT between `{` and the declaration made it fail
   * even when the value was right. `[^}]*?` accepts prose, which is what the declaration
   * now carries. And the assertion is `top: auto`, NOT `top:` -- a check that accepts any
   * value cannot tell the old contract from the new one, which is how F4 came to fail on the
   * pristine AND on all 11 mutants and lose its discrimination. */
  add('F4 while floated, the bar steps to the top and the caption RESTS ON THE BOTTOM',
    /body\[data-surface="strip"\]\[data-float="on"\] \.panel \{\s*inset:\s*0 0 auto 0/.test(css) &&
    /body\[data-surface="strip"\]\[data-float="on"\] \.caption-float \{[^}]*?top:\s*auto/.test(css),
    'panel inset:0 0 auto 0 + caption top:auto (bottom-anchored, owner 2026-10-15)');

  return out;
}

function report(label, rows) {
  console.log('THREE-OVERLAYS ORACLE -- ' + label);
  let bad = 0;
  for (const r of rows) {
    if (!r.ok) bad += 1;
    console.log('  ' + (r.ok ? 'ok  ' : 'FAIL') + '  ' + r.name.padEnd(58) + ' ' + r.detail);
  }
  console.log('');
  console.log(rows.length + ' check(s), ' + bad + ' failed');
  return bad;
}

const pristine = checks(PANEL);

if (!NEG) {
  const bad = report('PRISTINE (the shipped bytes)', pristine);
  console.log(bad === 0 ? 'VERDICT: PASS' : 'VERDICT: FAIL');
  process.exit(bad === 0 ? 0 : 1);
}

/* ---- NEGATIVE ARM ----------------------------------------------------- */
const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();
const scratch = fs.mkdtempSync(path.join(TMP, 'sotto-three-neg-'));
const FILES = ['panel.html', 'panel.css', 'panel.js', 'caption-float.js'];
for (const f of FILES) fs.copyFileSync(path.join(PANEL, f), path.join(scratch, f));

/* ONE mutant at a time; the scratch copy is reset to the pristine bytes before
   each mutation, so a mutant can only ever fail on its OWN account. */
const muts = [
  { tag: 'N1 the transparency trap is re-added (the reported bug)', file: 'panel.css',
    from: '/* ── 3. THE FLOATED CAPTION',
    to: 'body[data-surface="strip"][data-transparency="on"] .panel {\r\n  display: none;\r\n}\r\n\r\n/* ── 3. THE FLOATED CAPTION' },
  { tag: 'N2 the overlay gains a background (the owner: sem fundo)', file: 'panel.css',
    from: '.caption-float {', to: '.caption-float {\n  background: #0b0f14;' },
  { tag: 'N3 .history is un-hidden on the strip', file: 'panel.css',
    from: 'body[data-surface="strip"] .history,\r\n',
    to: '' },
  { tag: 'N4 the transparency button comes back to the strip', file: 'panel.html',
    from: 'id="strip-open-button"',
    to: 'id="strip-transparency-button"\n          aria-pressed="false"\n        >\n          <span class="strip-button__label">Transparency</span>\n        </button>\n        <button\n          type="button"\n          class="strip-button"\n          id="strip-open-button"' },
  { tag: 'N5 the strip shrinks back to a max-content pill', file: 'panel.css',
    from: 'body[data-surface="strip"] .panel {',
    to: 'body[data-surface="strip"] .panel {\r\n  width: max-content;' },
  { tag: 'N6 the breathing bar is deleted from the overlay', file: 'panel.html',
    from: '<span class="caption-float__led" aria-hidden="true"></span>\r\n        ', to: '' },
  { tag: 'N7 the OUVINDO... empty state is deleted', file: 'caption-float.js',
    from: "line.classList.toggle('is-empty', empty);", to: 'false;' },
  /* N8 IS THE CONTROL D1/D1b/D6 NEVER HAD, and that is why they could go red for a
     day without anyone reading it as "this gate pins a dead contract". It renames
     the open button into the theme button the owner cut, so ONE mutation moves
     three arms: D1 loses strip-open-button, D1b gains strip-theme-button, D6 sees
     the button it forbids. */
  { tag: 'N8 the strip theme button is restored (the owner cut it)', file: 'panel.html',
    from: 'id="strip-open-button"',
    to: 'id="strip-theme-button" data-theme-button' },
  /* N9/N10 ARE THE CONTROLS THE 2026-10-13 RE-BASELINE NEEDED: N9 removes the call
     that makes live-on mean caption-on-screen, N10 restores the removed Linhar
     button so D1/D1b can go red. */
  { tag: 'N9 the LIVE button no longer drives the caption (applyFloat call deleted)', file: 'panel.js',
    from: 'applyFloat(liveEnabled);', to: '' },
  { tag: 'N10 the removed Linhar button comes back (the owner moved the control to live)', file: 'panel.html',
    from: 'id="strip-open-button"', to: 'id="strip-float-button"' },
  /* N11 IS THE CONTROL THE 2026-10-14 D5 RE-BASELINE NEEDS. The owner removed the
     transcript BUTTON and kept the drawer behind it, so D5 now asserts BOTH halves;
     without a mutant that puts the button back, that gate could not tell the two
     apart and would pass just as well with the control restored. */
  { tag: 'N11 the transcript button comes back (the owner removed it)', file: 'panel.html',
    from: '<button\r\n            type="button"\r\n            class="history__path"',
    to: '<button type="button" class="history__toggle" id="history-toggle" aria-expanded="false" aria-controls="history-body" title="Expand the transcript">\r\n            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3.5L10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" /></svg>\r\n          </button>\r\n          <span\r\n            class="history__label"' },
];

let wrong = 0;
for (const m of muts) {
  for (const f of FILES) fs.copyFileSync(path.join(PANEL, f), path.join(scratch, f));
  const p = path.join(scratch, m.file);
  const cur = read(p);
  if (cur.indexOf(m.from) < 0) {
    console.error('SETUP ERROR: mutant anchor absent in ' + m.file + ': ' + JSON.stringify(m.from.slice(0, 70)));
    process.exit(2);
  }
  fs.writeFileSync(p, cur.replace(m.from, m.to));
  const rows = checks(scratch);
  const bad = rows.filter((r) => !r.ok);
  const red = bad.length > 0;
  if (!red) wrong += 1;
  console.log('  ' + (red ? 'RED  ' : 'GREEN') + '  ' + m.tag + '  -> ' + bad.length + ' failing check(s)' + (bad.length ? ': ' + bad.slice(0, 4).map((x) => x.name).join(' | ') : ''));
}
fs.rmSync(scratch, { recursive: true, force: true });
console.log('');
console.log(wrong === 0 ? 'NEG-ARM VERDICT: PASS -- every mutant went RED.' : 'NEG-ARM VERDICT: FAIL -- ' + wrong + ' mutant(s) stayed GREEN.');
process.exit(wrong === 0 ? 0 : 1);