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
];

const run = (cmd, args, label) => {
  const r = spawnSync(cmd, args, { cwd: 'H:/sotto', encoding: 'utf8', windowsHide: true,
    maxBuffer: 64 * 1024 * 1024, env: { ...process.env, TMPDIR: 'I:/cc-tmp' } });
  const text = (r.stdout || '') + (r.stderr || '');
  const tail = text.split(/\r?\n/).filter((l) =>
    /VERDICT|PASS \/|GREEN|SUMMARY|ARM-VERDICT|NEG-ARM|ORACLE|"verdict"/.test(l));
  if (r.status !== 0) {
    console.log('rc=' + r.status + ' !!! ' + label.padEnd(30) + (tail.slice(-1)[0] || text.split(/\r?\n/).filter(Boolean).slice(-1)[0] || '').trim().slice(0, 105));
  } else {
    console.log('rc=0  ' + label.padEnd(30) + (tail.slice(-1)[0] || '').trim().slice(0, 105));
  }
  return r.status === 0;
};

console.log('--- python oracles (' + py.length + ') ---');
let failed = 0;
for (const [a, l] of py) if (!run('py', ['-3', ...a.split(' ')], l)) failed += 1;
console.log('--- node oracles (' + node.length + ') ---');
for (const [a, l] of node) if (!run('node', a.split(' '), l)) failed += 1;
const total = py.length + node.length;
console.log('');
console.log('SUMMARY: ' + (total - failed) + '/' + total + ' instrument(s) rc=0; failed=' + failed
  + '; launches=0 (no shell, app or worker is opened -- the ONE run.cmd invocation in this list is'
  + ' its --help pre-flight, which argparse answers and exits; measured 2026-10-12: 0 processes left)');
process.exit(failed === 0 ? 0 : 1);