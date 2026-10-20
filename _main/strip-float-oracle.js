/* strip-float-oracle.js -- the S2 gate: the rebuilt strip and the floated caption.
 *
 * THE OWNER'S THREE DEMANDS, one check each (2026-10-12):
 *   1. *"nao deve aparecer nenhuma legenda la embaixo... ele deve ser menor ainda,
 *      mais estreito, do tamanho dos botoes"* -- the strip is 40px, sizes itself to its
 *      own content, and carries no caption row at all.
 *   2. *"e ele tem um botao de linhar a legenda, que liga ela NA TELA, igual um
 *      overlay, EXATAMENTE IGUAL os .zip fazem"* -- the Linhar button, the overlay, and
 *      the window height that only the shell can change.
 *   3. *"cada tema/template/design... e implementado"* -- the ten zip C designs are
 *      live manifest entries with a stylesheet behind each name.
 *
 * WHY A NEW ORACLE: `_main/letter-swap-oracle.js` gates the MODULE only (it runs
 * letter-swap.js in a vm against a fixture) and never looks at panel.js's call
 * site, so that wiring would be unguarded. And nothing covered the strip:
 * `--strip-height` was 100px and only an impression said so.
 *
 * `--neg-arm`: the same files copied with ONE behaviour removed each, and the SAME
 * checks re-run against the copies. Each mutant must go RED or the oracle cannot
 * say no, and the green is worth nothing. RE-BASELINED 2026-10-13 for the owner's
 * ruling that the LIVE button IS the caption control (*"o botao de legenda pra
 * ativar a legenda deve ser o botao 'live'. o botao 'live' ativo deve mostrar na
 * tela as legendas"*). Seven mutants:
 *   M1 the height goes back to the old 100px;
 *   M2 the applyFloat(liveEnabled) call is deleted (live no longer drives the caption);
 *   M3 the overlay push in addCaption is deleted;
 *   M4 the runtime height change through setStripHeight is deleted;
 *   M5 the overlay gains a background (the owner's *"sem fundo"*);
 *   M6 applyFloat becomes unconditional (the strip-only guard is removed);
 *   M7 the straight band gets its rounded pill corners back.
 */
'use strict';

const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

const ROOT = path.resolve(__dirname, "..");
const PANEL = path.join(ROOT, "app", "panel");

const NEG = process.argv.includes("--neg-arm");

const read = (p) => fs.readFileSync(p, "utf8");

/* THE SOURCE OF ONE FUNCTION, by brace matching.
 * RE-ANCHORED 2026-10-20 (lane caption): W10 used to measure `applyFloat` with a
 * REGEX SPREAD OVER THE WHOLE FILE (`/currentSurface\(\)\s*===\s*'strip'[\s\S]
 * {0,120}?bridge\.setPanelSurface\(.strip./`), which is a measurement of the
 * FILE, not of the FUNCTION -- it was green whenever those two strings happened
 * to be 120 characters apart anywhere in panel.js. It has to be the function's
 * OWN body, so the body is extracted and the check reads it. */
function functionSource(src, name) {
  const i = src.indexOf("function " + name);
  if (i < 0) return "";
  const open = src.indexOf("{", i);
  if (open < 0) return "";
  let depth = 0;
  for (let k = open; k < src.length; k += 1) {
    if (src[k] === "{") depth += 1;
    else if (src[k] === "}") { depth -= 1; if (depth === 0) return src.slice(i, k + 1); }
  }
  return "";
}

function checks(dir) {
  const html = read(path.join(dir, "panel.html"));
  const css = read(path.join(dir, "panel.css"));
  const js = read(path.join(dir, "panel.js"));
  /* THE CODE, WITHOUT ITS PROSE. panel.js documents the contract it USED to
     have in comments -- including the name of the constant it DELETED -- so a
     grep for a retired name must not read the note that explains the removal.
     The comments are stripped; the CODE is what is measured. */
  const jsCode = js.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^[ \t]*\/\/.*$/gm, " ");
  const float = read(path.join(dir, "caption-float.js"));
  const zipcJs = read(path.join(dir, "themes", "zipc-panels.js"));
  const zipcCss = read(path.join(dir, "themes", "zipc-panels.css"));
  const out = [];
  const add = (name, ok, detail) => out.push({ name, ok: !!ok, detail: String(detail == null ? "" : detail) });
  const has = (id) => html.includes("id=\"" + id + "\"");

  /* ---- 1. THE STRIP IS BUTTON-SIZED ------------------------------------- */
  const sh = /--strip-height\s*:\s*([^;]+);/.exec(css);
  add("S1 --strip-height is 40px, not the old 100px", !!sh && sh[1].trim() === "40px", sh ? sh[1].trim() : "ABSENT");
  const fh = /--float-height\s*:\s*([^;]+);/.exec(css);
  add("S2 --float-height exists (the raised height)", !!fh, fh ? fh[1].trim() : "ABSENT");
  const ss = !/body\[data-surface="strip"\]\s*\.panel\s*\{[^{}]*width:\s*max-content/.test(css);
  add("S3 the strip panel is NOT a max-content pill (2026-10-12: that rule WAS the owner's solid-colour bug)", ss, ss ? "no width:max-content (fixed)" : "width:max-content PRESENT = the bugthe strip surface");
  const nc = /body\[data-surface="strip"\]\s+\.captions\s*\{\s*display:\s*none/.test(css);
  add("S4 the strip carries no caption row", nc, nc ? ".captions display:none" : "no .captions display:none on the strip surface");
  const nb = /body\[data-surface="strip"\]\s*\{[^{}]*background:\s*transparent/.test(css);
  add("S5 the strip body is NOT transparent (re-baselined 2026-10-12: a transparent body let the shell's opaque #0B0F14 form colour show through as the owner's \"cor solida\", so the fix paints it)", !nb, !nb ? "body paints (fixed)" : "body still transparent = the solid-colour bug");
  const btn = /body\[data-surface="strip"\] \.strip-button\s*\{([^}]*)\}/.exec(css);
  if (!btn) {
    add("S6 the strip-button rule exists", false, "no .strip-button rule");
  } else {
    const b = btn[1];
    add("S6 the strip buttons are the lighter fill", /background:\s*rgba\(148,\s*163,\s*184,\s*0\.16\)/.test(b), "rgba(148,163,184,0.16)");
    add("S7 the strip buttons are the lighter border", /border-color:\s*rgba\(148,\s*163,\s*184,\s*0\.3\)/.test(b), "rgba(148,163,184,0.30)");
  }
  /* THE STRAIGHT BAND (owner, 2026-10-13: *"pro painel de baixo, ele tem que ser
     mais uma faixa/linha reta."*). The band rule is the strip .panel rule that
     carries border-radius: 0; the older strip .panel rule (the drag transform)
     must not be confused with it. */
  const cssDecls = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const band = /body\[data-surface="strip"\]\s*\.panel\s*\{([^}]*border-radius:\s*0[^}]*)\}/.exec(cssDecls);
  add("S21 the strip slab is a STRAIGHT BAND (radius 0, no gradient, flat fill, hairline top+bottom)",
    !!band && !/gradient/.test(band[1]) &&
    /border:\s*0;/.test(band[1]) &&
    /border-top:\s*1px solid var\(--line\)/.test(band[1]) &&
    /border-bottom:\s*1px solid var\(--line\)/.test(band[1]) &&
    /background:\s*rgba\(11,\s*15,\s*20,\s*0\.98\)/.test(band[1]),
    band ? (band[1].match(/border-radius:\s*[^;]+/) || ['?'])[0] : "no border-radius:0 strip .panel rule");

  /* ---- 2. THE LINHAR BUTTON AND THE OVERLAY --------------------------- */
  /* THE OWNER'S 2026-10-13 RULING: the caption control IS the live button. */
  add("S8 #strip-live-button is the ONE caption control in the markup", has("strip-live-button"), "present");
  add("S9 the separate Linhar button is GONE (one control, not two)", !has("strip-float-button"), has("strip-float-button") ? "STILL PRESENT" : "absent");
  add("S10 the live button carries aria-pressed (the state the overlay keys on)", /id="strip-live-button"[^>]*aria-pressed/.test(html), "present");
  add("S10b applyLiveEnabled drives applyFloat (live-on IS caption-on-screen, one fact)", /applyFloat\(liveEnabled\)/.test(js), "present");
  add("S11 #caption-float is in the markup", has("caption-float"), "present");
  for (const id of ["caption-float-line", "caption-float-prev", "caption-float-meter", "caption-float-meter-fill", "caption-float-credits"]) {
    add("S12 #" + id + " is in the markup", has(id), "present");
  }
  /* The owner: nothing on top of the current panel, nothing in its div. The
     document has exactly ONE <main>, so its close tag is the boundary. */
  const mc = html.indexOf("</main>");
  const fi = html.indexOf("id=\"caption-float\"");
  add("S13 the overlay is OUTSIDE <main class=panel>", mc >= 0 && fi > mc, "mainClose@" + mc + " float@" + fi);
  const cf = /\.caption-float\s*\{([^}]*)\}/.exec(css);
  add("S14 the overlay itself has no background", !!cf && !/background\s*:/.test(cf[1]), cf ? "no background on .caption-float" : "no .caption-float rule");
  const cs = /\.caption-float__stage\s*\{([^}]*)\}/.exec(css);
  add("S15 the overlay stage has no background", !!cs && !/background\s*:/.test(cs[1]), cs ? "no background on .caption-float__stage" : "no .caption-float__stage rule");
  add("S16 the overlay is scoped to the strip surface", /body\[data-surface="strip"\]\[data-float="on"\]\s+\.caption-float\s*\{\s*display:\s*block/.test(css), "present");

  add("S17 caption-float.js registers window.SottoCaptionFloat", /window\.SottoCaptionFloat\s*=/.test(float), "present");
  for (const k of ["push", "setMeter", "setListening", "state"]) {
    add("S18 SottoCaptionFloat." + k + " is exported", new RegExp("\\b" + k + "\\s*:").test(float), "present");
  }
  add("S19 the module resolves its nodes lazily (deferred-safe)", /getElementById\(.caption-float.\)/.test(float), "present");

/* THE ROW'S ORDER. A strip child with no `order` of its own falls back to 0, which
   TIES it with the brand and puts it ahead of every button declaring 1..7. Measured
   2026-10-12: Linhar rendered SECOND, right after the wordmark, while the paint below
   describes it as one of "the two ACTIONS at the end of the row". */
const orderMap = {};
/* RE-ANCHORED 2026-10-20 (lane caption). The old extractor demanded a rule whose
   WHOLE BODY was `order: N;` and whose selector was exactly
   `body[data-surface="strip"] <id>`. TWO things changed in the product and both
   are deliberate:
     - the X and the readout are pinned with `!important` AND ONE MORE CLASS
       than the contract's (`html body[data-surface="strip"] .stripbar
       #strip-hide-button`, panel.css:2117-2118) so the owner's X sits LAST
       whatever the contract sheet does with its own numbers;
     - the caption-size dial joined the row on 2026-10-18 (`order: 5`).
   The old extractor therefore read `hide=undefined state=undefined` -- a gate
   that could not see the two ENDS of the row it was measuring. The extractor
   below reads the ORDER of any strip-scoped rule, whatever else the rule
   carries, and it reads it from the CSS WITH ITS COMMENTS STRIPPED (a comment
   that talks about `order:` is prose, not a declaration). */
const cssNoComments = css.replace(/\/\*[\s\S]*?\*\//g, "\n");
const ruleRe = /([^{}]+)\{([^{}]*)\}/g;
let om;
while ((om = ruleRe.exec(cssNoComments)) !== null) {
  const sel = om[1].trim();
  if (sel.indexOf('data-surface="strip"') < 0) continue;
  const ord = /(?:^|;)\s*order:\s*(\d+)\s*(?:!\s*important\s*)?(?:;|$)/.exec(om[2]);
  if (!ord) continue;
  const ids = sel.match(/#[A-Za-z0-9_-]+/g);
  const key = (ids && ids.length) ? ids[ids.length - 1]
    : (sel.indexOf(".stripbar__brand") >= 0 ? ".stripbar__brand" : null);
  if (key) orderMap[key] = parseInt(ord[1], 10);
}
add("S20 the live button declares its own order (the default 0 would render it before the grip)",
  orderMap["#strip-live-button"] !== undefined,
  "order=" + orderMap["#strip-live-button"] + " of " + Object.keys(orderMap).length + " ordered children");
add("S20b the row order is brand<grip<live<open<font<pause<hide<state",
  orderMap["#strip-live-button"] > orderMap["#strip-drag-handle"] &&
  orderMap["#strip-live-button"] < orderMap["#strip-open-button"] &&
  orderMap["#strip-open-button"] < orderMap["#strip-font-scale-button"] &&
  orderMap["#strip-font-scale-button"] < orderMap["#strip-pause-button"] &&
  orderMap["#strip-pause-button"] < orderMap["#strip-hide-button"] &&
  orderMap["#strip-hide-button"] < orderMap["#strip-state"],
  "brand=" + orderMap[".stripbar__brand"] + " grip=" + orderMap["#strip-drag-handle"] + " live=" + orderMap["#strip-live-button"] + " open=" + orderMap["#strip-open-button"] + " font=" + orderMap["#strip-font-scale-button"] + " pause=" + orderMap["#strip-pause-button"] + " hide=" + orderMap["#strip-hide-button"] + " state=" + orderMap["#strip-state"]);

  /* ---- 3. panel.js WIRING ---------------------------------------------- */
  add("W1 dom.stripLiveButton is looked up", /stripLiveButton\s*:\s*document\.getElementById\(.strip-live-button.\)/.test(js), "present");
  add("W2 the live button is bound in wireStripControls", /stripLiveButton\.addEventListener\(.click./.test(js), "present");
  add("W3 addCaption pushes to the overlay", /SottoCaptionFloat\)\s*window\.SottoCaptionFloat\.push\(text,\s*meta/.test(js), "present");
  add("W4 renderProvisional pushes the forming line", /SottoCaptionFloat\)\s*\{\s*window\.SottoCaptionFloat\.push\(\(confWords/.test(js), "present");
  add("W5 paintLevel feeds the overlay meter", /SottoCaptionFloat\)\s*\{\s*window\.SottoCaptionFloat\.setMeter\(/.test(js), "present");
  add("W6 paintLevel feeds the overlay listening", /window\.SottoCaptionFloat\.setListening\(LEVEL\.have\)/.test(js), "present");
  /* W7 -- RE-ANCHORED 2026-10-20 (lane caption). The old check counted
   `bridge.setPanelSurface('strip', ...)` call sites in the RAW FILE, and it was
   GREEN ON A COMMENT: the only two `bridge.setPanelSurface('strip'` strings in
   panel.js live in the block comment that explains the three writes the owner
   had deleted (panel.js:2692-2700). A gate that counts the note explaining the
   removal is measuring prose, not the product. THE CONTRACT TODAY: the strip's
   height is the SHELL's (the caption is a native window), so the page asks the
   shell for the FULL PANEL and for NOTHING else -- and the count is read from
   the CODE, with the comments stripped. */
  const sps = (jsCode.match(/bridge\.setPanelSurface\([^)]*\)/g) || []);
  add("W7 the page asks the shell for the FULL PANEL only (the strip's height is the shell's)",
    sps.length === 1 && /bridge\.setPanelSurface\('panel'/.test(sps[0]),
    sps.length ? sps.join(" | ") : "NO LIVE CALL (the count was coming from a comment)");
  add("W8 the window height is THE ONE HEIGHT (2026-10-17: FLOAT_HEIGHT was DELETED, not re-tuned -- panel.js:62-85)",
    /const\s+STRIP_HEIGHT\s*=\s*'40px'/.test(jsCode) &&
    /setStripHeight\(STRIP_HEIGHT\)/.test(jsCode) &&
    !/FLOAT_HEIGHT/.test(jsCode),
    "STRIP_HEIGHT='40px' + setStripHeight(STRIP_HEIGHT) + no FLOAT_HEIGHT in the code");
  add("W9 the surface switch re-applies the live state (which repaints the float)", /function applySurface\(\)[\s\S]*?applyLiveEnabled\(liveEnabled,\s*\{\s*silent:\s*true\s*\}\)/.test(js), "present");
  /* W10 -- RE-ANCHORED 2026-10-20 (lane caption). The old W10 demanded that
     applyFloat call `bridge.setPanelSurface` behind a `currentSurface() ===
     'strip'` guard -- and it measured that with a REGEX SPREAD OVER THE WHOLE
     FILE, which is a measurement of the FILE, not of the FUNCTION. THE PRODUCT
     DELETED BOTH HALVES ON PURPOSE (panel.js:2692-2700, the owner's *"nao deve
     abrir qualquer coisa"*): the caption is a native window
     (`NativeCaptionOverlay`), the page's overlay is the FALLBACK for a shell
     without `setLiveEnabled`, and the three writes that used to resize the
     window are GONE. THE CONTRACT TODAY: applyFloat opens NOTHING on the shell
     -- it writes the attribute, the ONE height and the overlay -- and a shell
     that owns a caption window gets NOTHING from it at all. The body below is
     the FUNCTION's own body, extracted by brace matching. */
  const applyFloatSrc = functionSource(jsCode, "applyFloat");
  add("W10 applyFloat asks the shell NOTHING (2026-10-17: the caption window belongs to the shell -- panel.js:2692-2700)",
    applyFloatSrc.length > 0 && !/setPanelSurface/.test(applyFloatSrc) && /setStripHeight\(STRIP_HEIGHT\)/.test(applyFloatSrc),
    applyFloatSrc.length ? ("no setPanelSurface; " + (/setStripHeight\(STRIP_HEIGHT\)/.test(applyFloatSrc) ? "setStripHeight(STRIP_HEIGHT) present" : "setStripHeight MISSING")) : "applyFloat NOT FOUND");
  add("W10b a shell that owns a caption window gets NOTHING from applyFloat (the guard is load-bearing)",
    /if\s*\(\s*shellOwnsCaptionWindow\(\)\s*\)\s*return;/.test(applyFloatSrc),
    applyFloatSrc.length ? (/if\s*\(\s*shellOwnsCaptionWindow\(\)\s*\)\s*return;/.test(applyFloatSrc) ? "the native guard is present" : "THE NATIVE GUARD IS GONE") : "applyFloat NOT FOUND");

  /* ---- 4. ZIP C: THE TEN DESIGNS -------------------------------------- */
  const names = [...zipcJs.matchAll(/name:\s*'([^']+)'/g)].map(m => m[1]);
  const want = ["GlassCards", "Hairline", "Paper", "Quotes", "Ledger", "Feed", "Bubbles", "Timeline", "Chips", "Gutter"];
  add("Z1 the manifest carries all ten zip C names", want.every(n => names.includes(n)), names.join(", "));
  add("Z2 each entry has a file, swatch and group", /file:\s*'themes\/zipc-panels\.css'/.test(zipcJs) && /swatch:\s*'#[0-9A-Fa-f]{6}'/.test(zipcJs) && /group:\s*'zipc-panels'/.test(zipcJs), "present");
  const blocks = [...zipcCss.matchAll(/:root\[data-theme='([^']+)'\]/g)].map(m => m[1]);
  add("Z3 the stylesheet has a scope per design", want.every(n => blocks.includes(n)), blocks.length + " scope(s)");
  add("Z4 each design declares its own accent", (zipcCss.match(/--accent\s*:/g) || []).length >= 10, (zipcCss.match(/--accent\s*:/g) || []).length + " --accent");
  /* Z5 -- RE-ANCHORED 2026-10-20 (lane caption). The design's caption size is no
   longer a bare `13px` nor a bare `var(--size-closed)`: the caption-size dial
   landed on 2026-10-18 and every design now declares
   `font-size: calc(var(--size-closed) * var(--caption-scale))`
   (zipc-panels.css:114 and its nine siblings). The old pattern matched
   neither the `calc()` nor the scale, so it counted ZERO and the gate was red
   on a product that ships all ten sizes. The scale is now part of the
   contract, and the pattern says so. */
  const capSizes = (zipcCss.match(/\.caption__text\s*\{[^}]*font-size:\s*(?:\d+px|var\(--size-closed\)|calc\(var\(--size-closed\)\s*\*\s*var\(--caption-scale\)\))/g) || []).length;
  add("Z5 each design declares its own caption size (literal px, the --size-closed token or the --caption-scale dial)", capSizes >= 10, capSizes + " .caption__text font-size rules");
  add("Z6 panel.html loads the stylesheet", /<link rel="stylesheet" href="themes\/zipc-panels\.css" \/>/.test(html), "present");
  add("Z7 panel.html loads the manifest fragment", /<script src="themes\/zipc-panels\.js"><\/script>/.test(html), "present");

  /* ---- 5. THE TWO NEW MODULES ARE DEFERRED, NOT ON FIRST PAINT --------- */
  add("D1 letter-swap.js is deferred", /<script src="letter-swap\.js" defer>/.test(html), "present");
  add("D2 caption-float.js is deferred", /<script src="caption-float\.js" defer>/.test(html), "present");
  const scripts = [...html.matchAll(/<script[^>]*src="([^"]+)"[^>]*>/g)].map(m => m[1]);
  add("D3 panel.js stays eager (the renderer cannot be deferred)", scripts.some(s => /panel\.js$/.test(s)), scripts.join(", "));

  return out;
}

function report(label, rows) {
  console.log("STRIP-FLOAT ORACLE -- " + label);
  let bad = 0;
  for (const r of rows) {
    if (!r.ok) bad += 1;
    console.log("  " + (r.ok ? "ok  " : "FAIL") + "  " + r.name.padEnd(52) + " " + r.detail);
  }
  console.log("");
  console.log(rows.length + " check(s), " + bad + " failed");
  return bad;
}

const pristine = checks(PANEL);

if (!NEG) {
  const bad = report("PRISTINE (the shipped bytes)", pristine);
  console.log(bad === 0 ? "VERDICT: PASS" : "VERDICT: FAIL");
  process.exit(bad === 0 ? 0 : 1);
}

/* ---- NEGATIVE ARM ----------------------------------------------------- */
const TMP = process.env.TMPDIR && fs.existsSync(process.env.TMPDIR) ? process.env.TMPDIR : os.tmpdir();
const scratch = fs.mkdtempSync(path.join(TMP, "sotto-strip-neg-"));
const srcDir = PANEL;
fs.mkdirSync(path.join(scratch, "themes"), { recursive: true });
for (const f of ["panel.html", "panel.css", "panel.js", "caption-float.js", "themes/zipc-panels.js", "themes/zipc-panels.css"]) {
  fs.copyFileSync(path.join(srcDir, f), path.join(scratch, f));
}

const FILES = ["panel.html", "panel.css", "panel.js", "caption-float.js", "themes/zipc-panels.js", "themes/zipc-panels.css"];

/* ONE mutant at a time. The scratch copy is reset to the pristine bytes before
   each mutation, so a mutant can only ever fail on its OWN account -- a cumulative
   mutation would let M1 fail on M2's behalf and hide M2 entirely. */
const muts = [
  { tag: "M1 the height goes back to the old 100px", file: "panel.css", from: "--strip-height: 40px", to: "--strip-height: 100px" },
  { tag: "M2 the caption is no longer driven by live (the applyFloat call is deleted)", file: "panel.js", from: "applyFloat(liveEnabled);", to: "" },
  { tag: "M3 the overlay push in addCaption is deleted", file: "panel.js", from: "if (window.SottoCaptionFloat) window.SottoCaptionFloat.push(text, meta || null);", to: "" },
  /* M4 -- RE-ANCHORED 2026-10-20 (lane caption). The old anchor was
     `setStripHeight(on ? FLOAT_HEIGHT : STRIP_HEIGHT);`, the call the product
     DELETED on 2026-10-17 (there is ONE height now: `setStripHeight(STRIP_HEIGHT)`,
     panel.js:2734). With the anchor gone the negative arm died with
     "SETUP ERROR: mutant anchor absent" (rc=2) -- a broken instrument, not a
     red one. The MUTATION is the same one (the runtime height change is
     deleted); only the ANCHOR moved. */
  { tag: "M4 the runtime height change is deleted", file: "panel.js", from: "setStripHeight(STRIP_HEIGHT);", to: "" },
  /* M6 -- RE-ANCHORED 2026-10-20 (lane caption). The old anchor was the
     `currentSurface() === 'strip'` guard around the `bridge.setPanelSurface`
     call -- a call and a guard the product DELETED on 2026-10-17. The guard
     that is load-bearing TODAY is the NATIVE one: a shell that owns a caption
     window gets NOTHING from applyFloat (panel.js:2729), and W10b measures
     exactly that. Deleting it is the same class of defect the old mutant
     described: applyFloat acting on a shell that did not ask for it. */
  { tag: "M6 applyFloat becomes unconditional (the native-caption-window guard is removed)", file: "panel.js", from: "  if (shellOwnsCaptionWindow()) return;", to: "" },
  { tag: "M5 the overlay gains a background", file: "panel.css", from: ".caption-float__stage {", to: ".caption-float__stage {" + String.fromCharCode(10) + "  background: #0b0f14;" },
  /* M7 -- RE-ANCHORED 2026-10-20 (lane caption). The old anchor was the bare
     `border-radius: 0;`, and panel.css carries TWO of them: the FIRST (line
     1845) belongs to the accent bar, not to the strip slab -- so the mutation
     was landing on a rule nobody measures and S21 stayed green. The mutant was
     INERT and the pre-existing reds in the pristine were HIDING it (a mutant
     "went red" only because the shipped file was already red). The anchor is
     now the strip band's OWN block, verified to appear exactly once. The
     mutation is the same one: the rounded pill corners come back. */
  { tag: "M7 the straight band gets its rounded pill corners back", file: "panel.css", from: "  border-bottom: 1px solid var(--line);\r\n  border-radius: 0;\r\n  background: rgba(11, 15, 20, 0.98);", to: "  border-bottom: 1px solid var(--line);\r\n  border-radius: 10px;\r\n  background: rgba(11, 15, 20, 0.98);" },
];
let wrong = 0;
for (const m of muts) {
  for (const f of FILES) fs.copyFileSync(path.join(srcDir, f), path.join(scratch, f));
  const p = path.join(scratch, m.file);
  const cur = read(p);
  if (!cur.includes(m.from)) {
    console.error("SETUP ERROR: mutant anchor absent in " + m.file + ": " + JSON.stringify(m.from.slice(0, 60)));
    process.exit(2);
  }
  fs.writeFileSync(p, cur.replace(m.from, m.to));
  const rows = checks(scratch);
  const bad = rows.filter(r => !r.ok);
  const red = bad.length > 0;
  if (!red) wrong += 1;
  console.log("  " + (red ? "RED  " : "GREEN") + "  " + m.tag + "  -> " + bad.length + " failing check(s)" + (bad.length ? ": " + bad.slice(0, 4).map(x => x.name).join(" | ") : ""));
}
fs.rmSync(scratch, { recursive: true, force: true });
console.log("");
console.log(wrong === 0 ? "NEG-ARM VERDICT: PASS -- every mutant went RED." : "NEG-ARM VERDICT: FAIL -- " + wrong + " mutant(s) stayed GREEN.");
process.exit(wrong === 0 ? 0 : 1);
