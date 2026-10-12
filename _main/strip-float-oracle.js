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
 * say no, and the green is worth nothing. Five mutants:
 *   M1 the height goes back to the old 100px;
 *   M2 the Linhar button is deleted from the markup;
 *   M3 the overlay push in addCaption is deleted;
 *   M4 the runtime height change through setPanelSurface is deleted;
 *   M5 the overlay gains a background (the owner's *"sem fundo"*).
 */
'use strict';

const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

const ROOT = path.resolve(__dirname, "..");
const PANEL = path.join(ROOT, "app", "panel");

const NEG = process.argv.includes("--neg-arm");

const read = (p) => fs.readFileSync(p, "utf8");

function checks(dir) {
  const html = read(path.join(dir, "panel.html"));
  const css = read(path.join(dir, "panel.css"));
  const js = read(path.join(dir, "panel.js"));
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

  /* ---- 2. THE LINHAR BUTTON AND THE OVERLAY --------------------------- */
  add("S8 #strip-float-button is in the markup", has("strip-float-button"), "present");
  add("S9 the button carries data-strip-float", /data-strip-float/.test(html), "present");
  add("S10 the button is aria-pressed", /strip-float-button[^>]*aria-pressed/.test(html), "present");
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

  /* ---- 3. panel.js WIRING ---------------------------------------------- */
  add("W1 dom.stripFloatButton is looked up", /stripFloatButton\s*:\s*document\.getElementById\(.strip-float-button.\)/.test(js), "present");
  add("W2 the button is bound in wireStripControls", /stripFloatButton\.addEventListener\(.click./.test(js), "present");
  add("W3 addCaption pushes to the overlay", /SottoCaptionFloat\)\s*window\.SottoCaptionFloat\.push\(text,\s*meta/.test(js), "present");
  add("W4 renderProvisional pushes the forming line", /SottoCaptionFloat\)\s*\{\s*window\.SottoCaptionFloat\.push\(\(confWords/.test(js), "present");
  add("W5 paintLevel feeds the overlay meter", /SottoCaptionFloat\)\s*\{\s*window\.SottoCaptionFloat\.setMeter\(/.test(js), "present");
  add("W6 paintLevel feeds the overlay listening", /window\.SottoCaptionFloat\.setListening\(LEVEL\.have\)/.test(js), "present");
  const sps = (js.match(/bridge\.setPanelSurface\(.strip./g) || []).length;
  add("W7 the window height goes through setPanelSurface", sps >= 1, sps + " call site(s)");
  add("W8 the raised height is FLOAT_HEIGHT", /setStripHeight\(on\s*\?\s*FLOAT_HEIGHT\s*:\s*STRIP_HEIGHT\)/.test(js), "present");
  add("W9 the surface switch re-paints the float state", /paintFloatState\(\)/.test(js), "present");

  /* ---- 4. ZIP C: THE TEN DESIGNS -------------------------------------- */
  const names = [...zipcJs.matchAll(/name:\s*'([^']+)'/g)].map(m => m[1]);
  const want = ["GlassCards", "Hairline", "Paper", "Quotes", "Ledger", "Feed", "Bubbles", "Timeline", "Chips", "Gutter"];
  add("Z1 the manifest carries all ten zip C names", want.every(n => names.includes(n)), names.join(", "));
  add("Z2 each entry has a file, swatch and group", /file:\s*'themes\/zipc-panels\.css'/.test(zipcJs) && /swatch:\s*'#[0-9A-Fa-f]{6}'/.test(zipcJs) && /group:\s*'zipc-panels'/.test(zipcJs), "present");
  const blocks = [...zipcCss.matchAll(/:root\[data-theme='([^']+)'\]/g)].map(m => m[1]);
  add("Z3 the stylesheet has a scope per design", want.every(n => blocks.includes(n)), blocks.length + " scope(s)");
  add("Z4 each design declares its own accent", (zipcCss.match(/--accent\s*:/g) || []).length >= 10, (zipcCss.match(/--accent\s*:/g) || []).length + " --accent");
  const capSizes = (zipcCss.match(/\.caption__text\s*\{[^}]*font-size:\s*\d+px/g) || []).length;
  add("Z5 each design declares its own caption size", capSizes >= 10, capSizes + " .caption__text font-size rules");
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
  { tag: "M2 the Linhar button is deleted", file: "panel.html", from: "<button\r\n          type=\"button\"\r\n          class=\"strip-button strip-button--float\"\r\n          id=\"strip-float-button\"\r\n          data-strip-float\r\n          data-strip-float-state=\"off\"\r\n          title=\"Linhar a legenda: solta no ecra, sem painel\"\r\n          aria-label=\"Linhar a legenda\"\r\n          aria-pressed=\"false\"\r\n        >\r\n          <svg viewBox=\"0 0 16 16\" aria-hidden=\"true\">\r\n            <path\r\n              d=\"M2.4 3.2h11.2a.8.8 0 0 1 .8.8v8a.8.8 0 0 1-.8.8H2.4a.8.8 0 0 1-.8-.8V4a.8.8 0 0 1 .8-.8z\"\r\n              fill=\"none\"\r\n              stroke=\"currentColor\"\r\n              stroke-width=\"1.3\"\r\n            />\r\n            <path d=\"M5 6.4h6M5 9h4\" stroke=\"currentColor\" stroke-width=\"1.2\" stroke-linecap=\"round\" />\r\n          </svg>\r\n          <span class=\"strip-button__label\">Linhar</span>\r\n        </button>", to: "" },
  { tag: "M3 the overlay push in addCaption is deleted", file: "panel.js", from: "if (window.SottoCaptionFloat) window.SottoCaptionFloat.push(text, meta || null);", to: "" },
  { tag: "M4 the runtime height change is deleted", file: "panel.js", from: "setStripHeight(on ? FLOAT_HEIGHT : STRIP_HEIGHT);", to: "" },
  { tag: "M5 the overlay gains a background", file: "panel.css", from: ".caption-float__stage {", to: ".caption-float__stage {" + String.fromCharCode(10) + "  background: #0b0f14;" },
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
