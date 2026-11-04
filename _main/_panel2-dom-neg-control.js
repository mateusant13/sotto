'use strict';

/**
 * _panel2-dom-neg-control.js — THE NEGATIVE ARM of `_panel2-dom-probe.js`.
 *
 * WHAT IT IS. The panel probe asserts the CURRENT contract, and every arm it
 * re-baselined on 2026-10-19 has to be able to say NO. A probe whose arms
 * always pass is decoration, so this control copies `app/panel` aside, breaks
 * ONE thing in the copy, and runs the REAL probe against the copy
 * (`SOTTO_PANEL_DIR`, the door the probe's own header documents): the arm that
 * names that thing must go RED.
 *
 * THE THREE MUTANTS (one per re-baselined arm):
 *   1. the LIVE button paints its own wish again -> ARM T's "a click ASKS the
 *      shell and paints NOTHING" must fail;
 *   2. the STRIP's pause button opens the dialog again -> ARM D's "the STRIP's
 *      pause button IS the confirmation" must fail;
 *   3. the panel stops asking the shell to switch surface -> ARM O's "the
 *      panel asks the SHELL to switch surface" must fail.
 *   4. the lamp paints a state of its own -> ARM L's "the lamp starts RED"
 *      must fail (a lamp that cannot be wrong is not an indicator);
 *   5. the X stops being the last control -> ARM L's "the X is the LAST
 *      control the panel cluster PAINTS" must fail;
 *   6. the caption switch closes the panel again -> ARM L's "a click on the
 *      caption switch does NOT close the panel" must fail.
 *
 * Exit codes: 0 every mutant went RED as it must | 1 a mutant still passed
 * (the arm cannot fail) | 2 setup error.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const HERE = __dirname;
const REPO = path.join(HERE, '..');
const PANEL_SRC = path.join(REPO, 'app', 'panel');
const PROBE = path.join(HERE, '_panel2-dom-probe.js');

const MUTANTS = [
  {
    name: 'the LIVE button paints its own wish again',
    file: 'panel.js',
    from: '      requestCaptionOverlay(!liveEnabled);',
    to: '      applyLiveEnabled(!liveEnabled);\n      requestCaptionOverlay(!liveEnabled);',
    arm: 'a click ASKS the shell and paints NOTHING',
  },
  {
    name: "the STRIP's pause button opens the dialog again",
    file: 'panel.js',
    from: "      button.addEventListener('click', () => confirmPause());",
    to: "      button.addEventListener('click', () => openPauseConfirm(button));",
    arm: "the STRIP's pause button IS the confirmation: one click unloads",
  },
  {
    name: 'the panel stops asking the shell to switch surface',
    file: 'panel.js',
    from: "    bridge.setPanelSurface('panel', reason);",
    to: '    // MUTANT: the page switches itself instead of asking the shell.',
    arm: 'with the shell call present, the panel asks the SHELL to switch surface',
  },
  {
    name: 'the lamp paints a state of its own',
    file: 'panel.js',
    from: '  paintLiveLamps(liveEnabled);',
    to: '  paintLiveLamps(true); // MUTANT: the lamp believes what it wants.',
    arm: 'the lamp starts RED: the live caption is off',
  },
  {
    name: 'the X stops being the last control',
    file: 'panel.css',
    from: 'html body[data-surface="panel"] .panel__controls #hide-button { order: 99 !important; }',
    to: 'html body[data-surface="panel"] .panel__controls #hide-button { order: 1 !important; }',
    arm: 'the X is the LAST control the panel cluster PAINTS',
  },
  {
    name: 'the caption switch closes the panel again',
    file: 'panel.js',
    from: '      requestCaptionOverlay(!liveEnabled);',
    to: '      requestCaptionOverlay(!liveEnabled);\n      if (bridge && typeof bridge.hide === \'function\') bridge.hide(\'caption-on\');',
    arm: 'a click on the caption switch does NOT close the panel and does NOT move it',
  },
];

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dst, entry.name);
    if (entry.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

function main() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'panel2-neg-'));
  const rows = [];
  let bad = 0;
  try {
    for (const [i, m] of MUTANTS.entries()) {
      const dir = path.join(tmp, `mutant-${i}`);
      copyDir(PANEL_SRC, dir);
      const target = path.join(dir, m.file);
      const src = fs.readFileSync(target, 'utf8');
      if (!src.includes(m.from)) {
        rows.push({ mutant: m.name, ok: false, why: 'the text to break was not found verbatim' });
        bad += 1;
        continue;
      }
      fs.writeFileSync(target, src.replace(m.from, m.to), 'utf8');
      const run = spawnSync(process.execPath, [PROBE], {
        env: { windowsHide: true, ...process.env, SOTTO_PANEL_DIR: dir },
        encoding: 'utf8',
      });
      const out = `${run.stdout || ''}${run.stderr || ''}`;
      const failed = out.split('\n').filter((l) => l.startsWith('[FAIL] '));
      const hit = failed.some((l) => l.includes(m.arm));
      const ok = run.status !== 0 && hit;
      if (!ok) bad += 1;
      rows.push({
        mutant: m.name, arm: m.arm, rc: run.status,
        failed_arms: failed.length, the_arm_failed: hit, ok,
        why: ok
          ? 'the broken copy went RED on that arm: the arm can fail'
          : `the broken copy did NOT go RED on that arm (rc=${run.status}, ${failed.length} arm(s) failed)`,
      });
    }
  } finally {
    try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (err) { /* leave it */ }
  }
  for (const r of rows) {
    console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${r.mutant}`);
    console.log(`       arm    = ${r.arm || '-'}`);
    console.log(`       rc     = ${r.rc}`);
    console.log(`       why    = ${r.why}`);
  }
  console.log(`\nRESULT: ${bad ? `RED — ${bad} mutant(s) did not go RED` : 'GREEN'} — `
    + `${rows.length - bad}/${rows.length} mutant(s) went RED as they must`);
  process.exit(bad ? 1 : 0);
}

main();
