// Sotto -- the IN-PROCESS instrument battery. Launches NOTHING.
//
// WHY THIS FILE EXISTS: the 24-instrument battery this session has been running lived in
// `I:\cc-tmp\final-battery.mjs`, which is NOT in the repo -- so the substitute gate for the owner
// stop order (see AGENTS.md: `_audit-verify-all.cmd` launches the shell dozens of times and is
// FORBIDDEN while the order lasts) was reproducible only on this box. This is that battery, committed,
// with every instrument this session added and with BOTH COLOURS of each (`--neg-arm`).
//
// WHAT IT IS NOT: it is not a substitute for the launch battery's PAINTED claims. Everything here is
// bytes, parse, in-process drive or a passive process/window read. Nothing opens the shell or the worker.
import { spawnSync } from 'node:child_process';

const py = [
  ['_main/canonical-producer-oracle.py', 'canonical-producer 47/47'],
  ['_main/meter-chain-oracle.py', 'meter-chain 55'],
  ['_main/meter-chain-oracle.py --neg-arm', 'meter-chain neg 66'],
  ['_main/audio-meter-oracle.py', 'audio-meter 11'],
  ['_main/audio-meter-oracle.py --neg-cadence', 'audio-meter neg-cadence'],
  ['_main/redux-arm-weights-oracle.py', 'redux-arm-weights 20'],
  ['_main/per-app-source-plumbing-oracle.py', 'per-app-source'],
  ['_main/app-target-oracle.py', 'app-target 9/9'],
  ['_main/audit-rows-tap-flags-ledger.py', 'tap-flags-ledger'],
  ['_main/audit-rows-bridge-decisions.py', 'bridge-decisions 10 arms'],
  ['_main/audit-rows-bridge-decisions.py --neg-arm', 'bridge-decisions neg'],
  ['_main/audit-rows-byte-claims.py', 'byte-claims'],
  ['_main/audit-rows-negative-arm-falsifiability.py', 'neg-arm-falsifiability'],
  ['_main/audit-rows-landmine-child-control.py', 'landmine-child-control'],
  ['_main/_oss_oracle.py', 'oss-oracle 4/4'],
  ['_main/model-spec-oracle.py', 'model-spec'],
  ['_main/stale-receipt-oracle.py', 'stale-receipt (row #29)'],
  ['_main/stale-receipt-oracle.py --neg-arm', 'stale-receipt neg'],
  ['_main/device-ladder-doc-oracle.py', 'ladder-doc (row #23)'],
  ['_main/device-ladder-doc-oracle.py --neg-arm', 'ladder-doc neg'],
  ['_main/panel-visibility-guard-oracle.py', 'visibility-guard (rows #60/#61)'],
  ['_main/panel-visibility-guard-oracle.py --neg-arm', 'visibility-guard neg'],
  ['_main/panel-window-census.py', 'panel-census 7 tests'],
  ['_main/panel-window-census.py --neg-arm', 'panel-census 7 mutants'],
  ['_main/inherited-row-reconciler.py', 'inherited-rows reconciled'],
  ['_main/inherited-row-reconciler.py --neg-arm', 'inherited-rows neg'],
  ['_main/child-channel-oracle.py', 'child-channel (row #5)'],
  ['_main/offscreen-cure-comment-oracle.py', 'offscreen-comments (row #33)'],
  ['_main/offscreen-cure-comment-oracle.py --neg-arm', 'offscreen-comments neg'],
  ['_main/panel-exit3-oracle.py --unit --neg-arm', 'panel-exit3 unit+neg (rows #27/#64)'],
  ['_main/selftest-focus-oracle.py', 'selftest-focus (rows #28/H6/B)'],
  ['_main/selftest-focus-oracle.py --neg-arm', 'selftest-focus neg'],
  ['_main/cited-instruments-oracle.py', 'cited-instruments (evidence chain)'],
  ['_main/cited-instruments-oracle.py --neg-arm', 'cited-instruments neg'],
  ['_main/device-ladder-rescan-oracle.py', 'ladder-rescan (row F15)'],
  ['_main/device-ladder-rescan-oracle.py --neg-arm', 'ladder-rescan neg'],
  ['_main/selftest-quality-oracle.py', 'selftest-quality (rows #25/H1)'],
  ['_main/selftest-quality-oracle.py --neg-arm', 'selftest-quality neg'],
  ['_main/panel-flash-contradiction-oracle.py', 'flash-contradiction (rows #46/F3)'],
  ['_main/panel-flash-contradiction-oracle.py --neg-arm', 'flash-contradiction neg'],
  ['_main/worker-eof-contract-oracle.py', 'worker-eof-contract (row F18)'],
  ['_main/worker-eof-contract-oracle.py --neg-arm', 'worker-eof-contract neg'],
  ['_main/channel-class-site-oracle.py', 'channel-class-site (rows #5/F1)'],
  ['_main/channel-class-site-oracle.py --neg-arm', 'channel-class-site neg'],
  ['_main/run-cmd-verdict-attribution-oracle.py', 'verdict-attribution (rows #30/#C)'],
  ['_main/run-cmd-verdict-attribution-oracle.py --neg-arm', 'verdict-attribution neg'],
  ['_main/runcmd-arm-coverage-oracle.py', 'runcmd-arm-coverage (rows #58/#D)'],
  ['_main/runcmd-arm-coverage-oracle.py --neg-arm', 'runcmd-arm-coverage neg'],
  ['_main/wasapi-buffer-fallback-oracle.py', 'wasapi-buffer-fallback (row F3)'],
  ['_main/wasapi-buffer-fallback-oracle.py --neg-arm', 'wasapi-buffer-fallback neg'],
  ['_main/ready-stream-blindness-oracle.py', 'ready-stream-blindness (row #18)'],
  ['_main/ready-stream-blindness-oracle.py --neg-arm', 'ready-stream-blindness neg'],
  ['_main/staging-hang-artefact-oracle.py', 'staging-hang-artefact (row #19)'],
  ['_main/staging-hang-artefact-oracle.py --neg-arm', 'staging-hang-artefact neg'],
  ['_main/preflight-refusal-visible-oracle.py', 'preflight-refusal-visible (row G5)'],
  ['_main/webview-shell-field-count-oracle.py', 'webview-shell-field-count (row F9)'],
  ['_main/webview-shell-field-count-oracle.py --neg-arm', 'webview-shell-field-count neg'],
  ['_main/timeout-tree-ceiling-oracle.py', 'timeout-tree-ceiling (row #62)'],
  ['_main/panel-flash-numbers-reconciliation-oracle.py', 'panel-flash-numbers (rows #4/F1)'],
  ['_main/panel-search-keyboard-oracle.py', 'panel-search-keyboard (row F9)'],
  ['_main/rtf-cpu-attribution-oracle.py', 'rtf-cpu-attribution (row F10)'],
  ['_main/unfinished-items-coverage-oracle.py', 'unfinished-items coverage (every named source)'],
  ['_main/unfinished-items-coverage-oracle.py --neg-arm', 'unfinished-items coverage control'],
  ['_main/verify-all-launch-audit.py', 'verify-all starts nothing (precondition for running it)'],
  ['_main/agents-md-pins-oracle.py', 'AGENTS.md pins re-measured live (the --help size and the battery pin)'],
  ['_main/agents-md-pins-oracle.py --neg-arm', 'agents-md-pins neg (the mutated doc copy must go RED)'],
  // THE GATE FOR THE DEFECT THAT COST 2.5 h. The handler map was a bare dict
  // literal, so ONE bad entry killed dispatch for EVERY page->shell kind and the
  // shell own log said NOTHING. This calls the REAL dispatch with a kind nobody
  // knows; building the map IS the test. Nothing launched.
  ['_main/bridge-handler-map-oracle.py', 'handler-map (the 2.5 h outage)'],
  ['_main/bridge-handler-map-oracle.py --neg-arm', 'handler-map neg'],
  // REGRA 10, made permanent: the shipped cinematic.css must be reproduced by a
  // fresh run of its generator. Seeds the backdrops (or fetch_backdrop downloads)
  // and themes.js (the generator READS the manifest it replaces).
  ['_main/gen-cinematic-repro-oracle.py', 'generator reproduces (regra 10)'],
  ['_main/gen-cinematic-repro-oracle.py --neg-arm', 'generator repro neg'],
  // The SAME rule for the other generator, and it is the net under the pending
  // --size-meta fix: that fix edits gen_themes.py, which writes panel-designs.css.
  ['_main/gen-themes-repro-oracle.py', 'theme gen reproduces (regra 10)'],
  ['_main/gen-themes-repro-oracle.py --neg-arm', 'theme gen repro neg'],
  // THE STRIP DRAG, SHELL HALF. The half that MOVES THE WINDOW, driven directly on a
  // fake object: offset applied exactly, no resize, clamp load-bearing, refusal
  // off-strip. Nothing launched.
  ['_main/strip-drag-shell-oracle.py', 'strip drag: shell half'],
  ['_main/strip-drag-shell-oracle.py --neg-arm', 'strip drag shell neg'],
  // THE CLASS THAT COST THE DRAG. panel.html declares script-src self with no
  // unsafe-inline, and such a CSP BLOCKS inline scripts and inline handlers --
  // silently. The drag handler was the only inline script and it never ran.
  ['_main/csp-inline-oracle.py', 'CSP: no inline scripts'],
  ['_main/csp-inline-oracle.py --neg-arm', 'CSP inline neg'],
  ['_main/cobertura-oracle.py', 'cobertura: 34 areas'],
  ['_main/photo-scrim-census.py', 'photo scrim: 25 themes'],
  ['_main/photo-scrim-census.py --neg-arm', 'photo scrim neg: zeroed scrim RED'],
  ['_main/aceitacao-gate.py', 'aceitacao: every PROVADO names a gate'],
  ['_main/panel-chrome-marks-oracle.py', 'panel chrome marks: 6 rows'],
  ['_main/start-menu-shortcut-gate.py', 'windows search shortcut'],
  ['_main/battery-rows-gate.py', 'battery rows: 142'],
  ['_main/run-cmd-refusal-path-oracle.py', 'refusal path resolved, not hand-written'],
  ['_main/surface-loop-oracle.py', 'surface loop guard (JS<->Python)'],
  // 2026-10-20: this instrument was listed TWICE in this runner -- here, and
  // again in the LANE C block below under a second label. Same file, same
  // command, so the second run only repeated the first one's verdict. The row
  // in the LANE C block stays (it sits next to its own negative arm) and this
  // one is gone.
  // The same duplication, found in the SAME audit: `preflight-refusal-visible-
  // oracle.py` was listed twice as well -- once in the block above (label
  // "preflight-refusal-visible (row G5)") and once here. Identical command,
  // identical verdict, one wasted run. The row above stays; this one is gone.
  // (Its negative arm is NOT listed anywhere -- that gap is a RECEIPT to open,
  // not a row to invent here.)
  // A ULTIMA LACUNA (LANE B, 2026-10-15). O gate do painel escondido no arranque vive
  // no shell, e o oraculo JA EXISTIA -- estava de fora porque uma nota anterior o
  // descrevia como "escreve e corre copias do shell". MEDIDO por mim antes de o
  // registar: e HEADLESS BY CONSTRUCTION (nenhuma janela, nenhum WebView2), escreve os
  // mutantes num TemporaryDirectory e importa-os; a prova e um census meu a volta da
  // corrida -- visible_windows=11 antes e 11 depois, python_procs=15 antes e 15 depois.
  // 144 decisoes de visibilidade, 4 mutantes (3 'caught' + 1 'immune' de controlo),
  // ORACLE GREEN failures=0, rc=0, 1.4 s.
  ['_main/panel-hidden-at-startup-oracle.py', 'panel hide gate at startup (headless, 4 mutants)'],
  // LANE A (2026-10-15): THE TWO HALVES OF THE JS<->PYTHON SURFACE LOOP GUARD, and
  // the negative arm of the row above. The shell half drives the REAL
  // SottoHost.dispatch -> SottoShell.set_panel_surface; measured 200 echoes -> 1
  // application, and 203 applications with the guard deleted (the p99 264/s loop
  // that froze the box). The page half is a .js row below.
  ['_main/surface-loop-oracle.py --neg-arm', 'surface loop neg: shell guard deleted -> RED'],
  // THE ATOMIC PANEL DUMP -- the fixed temp name that produced 1 145 063 write
  // failures and the bounded rename retry that absorbs the PermissionError storm
  // two writers produce. Registered here because the area's token only LOOKED
  // covered: the row naming panel-state-guard-gate.js gates a DIFFERENT property.
  ['_main/panel-state-atomic-oracle.py', 'panel state atomic write (1 145 063 failures)'],
  ['_main/panel-state-atomic-oracle.py --neg-arm', 'panel state atomic neg: both halves RED'],
  ['_main/log-rotation-oracle.py', 'log rotation (cap 64 MB)'],
  ['_main/queue-drops-whitelist-oracle.py', 'queue_drops whitelist'],
  ['_main/second-pass-default-oracle.py', 'second pass is opt-in'],
  ['_main/emit-queue-bound-oracle.py', 'emit queue bound'],
  ['_main/theme-lightness-census.py --gate', 'no theme ships light'],
  ['_main/cine-themes-oracle.py', 'cine themes fidelity'],
  ['_main/cinematic-designs-oracle.py', 'cinematic designs fidelity'],
  ['_main/zipc-designs-oracle.py', 'zipc designs fidelity'],
  ['_main/caption-lines-oracle.py', 'caption lines fidelity'],
  // ── LANE C: the themes + hotkey gaps. Each area gets BOTH colours: the live
  // row and the row that proves the instrument can say NO.
  // The Alt+C contract is the 1/2/3 GESTURE today (one = the caption, two =
  // the FIRST panel, three = the RIGHT panel, inside a 250 ms window) -- the
  // three-state cycle of 2026-10-13 was retired by the owner on 2026-10-18
  // (app/webview/sotto_webview.py:7780), and this instrument was re-anchored
  // to the gesture on 2026-10-20. The row stays in the list: the acceptance
  // register cites it (_main/aceitacao-dono.md A1 and D4) and
  // _main/aceitacao-gate.py requires a cited instrument to be LISTED here.
  ['_main/hotkey-cycle-oracle.py', 'Alt+C gesture 1/2/3 (caption, 1st, right)'],
  ['_main/hotkey-cycle-oracle.py --neg-arm', 'Alt+C gesture neg (3 mutants)'],
  ['_main/panel-chrome-gate.py', 'panel chrome: footer labels, no browser'],
  ['_main/panel-chrome-gate.py --neg-arm', 'panel chrome neg (3 mutants)'],
  ['_main/theme-lightness-census.py --neg-arm', 'no white theme: neg (white injected)'],
  ['_main/cine-themes-oracle.py --neg-arm', 'cine themes neg (8 mutants)'],
  ['_main/cinematic-designs-oracle.py --neg-arm', 'cinematic designs neg (6)'],
  ['_main/zipc-designs-oracle.py --neg-arm', 'zipc designs neg (6)'],
  // ── LANE B: SHELL / LOG / WORKER (2026-10-15). As linhas verdes de B2/B4/B5/B6
  // ja estao acima (log-rotation, emit-queue-bound, queue-drops, second-pass) e passam
  // a correr os instrumentos ja com a forma de gate; o que falta aqui e o BRACO
  // NEGATIVO de cada uma -- um oraculo que nao sabe dizer NAO nao distingue a cura da
  // ausencia de teste (F2) -- mais as duas areas que nao tinham linha nenhuma (B1 e B3).
  //
  // B1 e o unico que invoca o run.cmd. Os bracos `start` deste oraculo ARRANCAM a app e
  // os G1..G4 arrancam copias dela, por isso o que corre aqui e
  // `--arms bogus,help --no-gaps`: o pre-flight recusa o --bogus-flag e o --help e
  // respondido pelo argparse -- nada chega ao caminho de lancamento. A prova e do
  // proprio oraculo, que a imprime: `leftovers=[]` e o census com 0 amostras visiveis.
  ['_main/run-cmd-exit-oracle.py --arms bogus,help --no-gaps', 'run-cmd exit: pre-flight arms (launch-free)'],
  ['_main/run-cmd-exit-oracle.py --arms bogus,help --no-gaps --neg-arm', 'run-cmd exit neg: pre-fix wrapper, arm1 RED'],
  // O DEFEITO DO rc 120 TEM O SEU PROPRIO CONTROLO: o pre-fix acima nao pode ser o
  // controlo desta cura (nao tem pre-flight nenhum), por isso `--temp-arm` restaura o
  // alvo %TEMP% numa copia e exige RED. E estatico: nao arranca um unico processo.
  ['_main/run-cmd-exit-oracle.py --temp-arm', 'run-cmd temp-arm: rc 120 defect restored -> RED'],
  ['_main/log-flood-census.py --gate', 'log flood census gate: 4 events / 97 %'],
  ['_main/log-flood-census.py --neg-arm', 'log flood census neg: synthetic flood must be RED'],
  ['_main/log-rotation-oracle.py --neg-arm', 'log rotation neg: trigger removed in a copy'],
  ['_main/emit-queue-bound-oracle.py --neg-arm', 'emit queue bound neg: guard removed'],
  ['_main/queue-drops-whitelist-oracle.py --neg-arm', 'queue_drops neg: field filtered out again'],
  ['_main/second-pass-default-oracle.py --neg-arm', 'second pass neg: default flipped to ON'],
];

const node = [
  ['_main/join-harness.js', 'join-harness 11 arms'],
  ['_main/join-harness.js --neg-arm', 'join-harness neg'],
  ['_main/caption-renderer-integration.js', 'renderer-integration 7'],
  ['_main/caption-renderer-integration.js --neg-arm', 'renderer-integration neg'],
  ['_main/scope-leak-oracle.js', 'scope-leak 8 sheets'],
  ['_main/scope-leak-oracle.js --neg-arm', 'scope-leak neg'],
  ['_main/redux-live-contract-oracle.js', 'redux-live-contract 8/8'],
  ['_main/panel-row-identity-oracle.js', 'panel-row-identity'],
  ['_main/historico-vs-redux-probe.js', 'historico-vs-redux GREEN'],
  ['_main/history-producer-gate.js', 'history-producer-gate (row F2, was un-gated)'],
  ['_main/history-producer-gate.js --control-stamp-nvidia', 'history-producer-gate control'],
  ['_main/letter-swap-oracle.js', 'letter-swap 84/84'],
  ['_main/letter-swap-oracle.js --neg-arm', 'letter-swap neg 4/4 RED'],
  ['_main/caption-independent-oracle.js', 'caption independent of panel'],
  // MEASURED 2026-10-20: these two negative arms were NOT listed, because
  // they were BROKEN (rc=2, SETUP ERROR -- the mutant anchors still pointed
  // at the retired contract). Re-anchored, they work (rc=0, 'every mutant
  // went RED') -- and a negative arm that is not listed is a mutant nobody
  // ever looks at again.
  ['_main/caption-independent-oracle.js --neg-arm', 'caption independent neg (10 mutants)'],
  ['_main/three-overlays-oracle.js', 'three overlays'],
  ['_main/three-overlays-oracle.js --neg-arm', 'three overlays neg (11/11)'],
  ['_main/strip-drag-loop-oracle.js', 'strip drag: the loop (clientX vs screenX)'],
  ['_main/strip-float-oracle.js', 'strip float oracle'],
  ['_main/strip-float-oracle.js --neg-arm', 'strip float neg (7 mutants)'],
  ['_main/panel-state-guard-gate.js', 'panel state guard'],
  ['_main/botoes-lane-oracle.js', 'botoes lane oracle'],
  // LANE A: the negative arm of the row above -- 8 mutants, one per arm of the
  // owner's own order, every one of them RED (measured 39 s). Without this row the
  // buttons area ran only its green arm inside the gate.
  ['_main/botoes-lane-oracle.js --neg-arm', 'botoes lane neg 8/8 RED'],
  ['_main/botoes-lane-gesture-oracle.js', 'botoes lane gesture'],
  // ── LANE C, the JS half of the same two gaps.
  ['_main/theme-switch-oracle.js', 'theme switching: ONE attribute write'],
  ['_main/theme-switch-oracle.js --neg-arm', 'theme switching neg (3 mutants)'],
  ['_main/fonts-fidelity-oracle.mjs', 'fonts fidelity (the .zip faces)'],
  ['_main/fonts-fidelity-oracle.mjs --neg-arm', 'fonts fidelity neg (face deleted)'],
  // LANE A: THE PAGE HALF of the same loop -- the shipped panel.html + panel.css +
  // the document's own script list (13 scripts), in jsdom, against a bridge that
  // answers a setPanelSurface ask the way the real shell does (surface + geometry
  // echo). It counts the page->shell asks, which is the audit's own metric, and
  // BOTH page guards are load-bearing: 5 of 6 arms RED for each mutant, measured.
  ['_main/surface-loop-panel-oracle.js', 'surface loop: page half (echo asks nothing)'],
  ['_main/surface-loop-panel-oracle.js --neg-arm', 'surface loop page neg: both guards RED'],
];

// ── WHAT THIS BATTERY IS, AND WHAT IT IS NOT ─────────────────────────────────
// IT IS AN INVENTORY: "this instrument EXISTS, it RUNS, and it is not broken".
// IT IS NOT the gate of CONVENTIONS. The house battery (`_main/_audit-verify-all.cmd`)
// is where the `:expectred` contract lives -- a negative arm has to exit the code the
// house expects. This file does not require any arm to exit a particular code, and it
// says so here so that nobody reads a green here as "the house convention holds".
//
// SO THE RC RULE IS PER ARM KIND, and it is the ONLY thing this runner judges BY RC:
//   NORMAL entry (no --neg*)
//       rc has to be 0. Anything else = the instrument is BROKEN: a check failed, or
//       it crashed.
//   NEGATIVE entry (--neg-arm / --neg-cadence / --control-stamp-nvidia)
//       rc 0 or 1 = the negative arm RAN, which is what is expected: the arm has to
//       be RED, and the instruments in this house are split between the two
//       conventions (some exit 1 when they catch the mutant, some exit 0).
//       rc >= 2 = a REAL failure: a setup error, an anchor that is missing or
//       ambiguous, a mutant that changed nothing. Those are BROKEN instruments and
//       they are reported as failures.
//
// WHY THIS MATTERS (measured 2026-10-20): the OLD runner read `r.status !== 0` as a
// failure, so the negative arms that exit 1 BY DESIGN were reported as RED -- and
// the noise HID the real reds (the ones whose anchor had gone stale, rc=2)
// underneath them. A false red on top of a real red is the worst kind of noise: it
// makes the reader stop looking.
//
// AND THE TWO THINGS THE RC ALONE CANNOT SEE (measured the same day, and both are
// read out of the OUTPUT -- they add NO red that the old rule did not already have;
// they only stop the new rc rule from DROPPING a real red):
//   1. A CRASH. The convention is rc=1 when the negative arm CATCHES the mutant, so
//      a Python traceback (rc=1) looks exactly like a caught mutant. Only the
//      traceback tells them apart. THE TRACEBACK HAS TO COME WITH A NON-ZERO RC: an
//      arm that PRINTS a traceback on purpose (to prove that a guard re-raises) and
//      still exits 0 is working, not broken.
//   2. AN ARM THAT REPORTS ITS OWN FAILURE. The convention is rc=0 when a mutant
//      SURVIVES, and 0 is also the code of a negative arm that did its job under the
//      other convention -- so the rc cannot tell a surviving mutant from a caught
//      one. The arm's OWN verdict line can, and the verdict line of every entry is
//      printed, so a reader can always see what the arm said.
const NEG_FLAGS = ['--neg-arm', '--neg-cadence', '--control-stamp-nvidia'];

const isNegativeArm = (args) => args.some((a) => NEG_FLAGS.includes(a));

const CRASHED = /Traceback \(most recent call last\):/;
const ARM_FAILED = /VERDICT[^\n]*\bFAIL\b|mutant anchor not found/;

const run = (cmd, args, label) => {
  // A PER-INSTRUMENT TIMEOUT, so one hung instrument cannot take the whole
  // battery down with it. MEASURED 2026-10-20: a run was killed at minute 3
  // and the instrument that came next (the Lead's
  // `panel-hidden-at-startup-oracle.py`, 2 s on its own) was innocent --
  // `spawnSync` without a timeout waits for ever, and the box was busy.
  // 300 s is far above the slowest instrument measured (60 s) and far below
  // 'the operator gave up'. A timeout is reported as a failure of THAT
  // instrument, with the reason -- the summary still comes out.
  const r = spawnSync(cmd, args, { cwd: 'H:/sotto', encoding: 'utf8', windowsHide: true,
    maxBuffer: 64 * 1024 * 1024, timeout: 300000,
    env: { ...process.env, TMPDIR: 'I:/cc-tmp' } });
  const text = (r.stdout || '') + (r.stderr || '');
  const tail = text.split(/\r?\n/).filter((l) =>
    /VERDICT|PASS \/|GREEN|SUMMARY|ARM-VERDICT|NEG-ARM|ORACLE|"verdict"/.test(l));
  const verdict = (tail.slice(-1)[0]
    || text.split(/\r?\n/).filter(Boolean).slice(-1)[0] || '').trim().slice(0, 105);
  const neg = isNegativeArm(args);
  const status = r.status;
  const timedOut = !!r.error && r.error.code === 'ETIMEDOUT';
  const crashed = status !== 0 && CRASHED.test(text);
  const armFailed = ARM_FAILED.test(verdict);
  const ok = neg
    ? (status === 0 || status === 1) && !crashed && !armFailed && !timedOut
    : (status === 0) && !armFailed && !timedOut;
  const why = timedOut ? 'TIMED OUT (300 s): the instrument hung -- the battery says so instead of dying with it'
            : crashed ? 'CRASHED (a traceback): the instrument is BROKEN'
            : armFailed ? 'the arm says in its own verdict that it is BROKEN'
            : neg ? 'a NEGATIVE arm that did not even RUN (rc>=2 = setup error)'
            : 'the instrument is BROKEN';
  if (ok) {
    console.log('rc=' + status + '  ' + label.padEnd(30) + verdict);
  } else {
    console.log('rc=' + (timedOut ? 'TIMEOUT' : status) + ' !!! ' + label.padEnd(30) + verdict + '   <-- ' + why);
  }
  return ok;
};

console.log('--- python oracles (' + py.length + ') ---');
let failed = 0;
for (const [a, l] of py) if (!run('py', ['-3', ...a.split(' ')], l)) failed += 1;
console.log('--- node oracles (' + node.length + ') ---');
for (const [a, l] of node) if (!run('node', a.split(' '), l)) failed += 1;
const total = py.length + node.length;
console.log('');
console.log('SUMMARY: ' + (total - failed) + '/' + total + ' instrument(s) OK under the rule above'
  + ' (a normal entry has to be rc=0 and must not report itself broken; a negative arm has to be'
  + ' rc=0 or rc=1, rc>=2 is a real failure, and a crash or an arm that reports its own failure'
  + ' is broken too); failed=' + failed
  + '; launches=0 (no shell, app or worker is opened -- the ONE run.cmd invocation in this list is'
  + ' its --help pre-flight, which argparse answers and exits; measured 2026-10-12: 0 processes left)');
process.exit(failed === 0 ? 0 : 1);