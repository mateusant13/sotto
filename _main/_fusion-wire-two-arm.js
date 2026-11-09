'use strict';

/**
 * _fusion-wire-two-arm.js -- the TWO-ARM number for the fusion wiring.
 *
 * The question Main asked, in one measurement: after a line CLOSES, what does
 * each surface carry -- the LIVE row the owner reads, and the HISTORY line the
 * panel commits -- and does the wiring change the DEFAULT (switch off)?
 *
 * THE TWO ARMS drive the REAL renderer (`app/panel/caption-formulation.js`, the
 * file `panel.html` loads), with the SAME stream partial in both:
 *
 *   raw    the CLOSED line is the finisher's text, untouched (the pipeline as it
 *          shipped: the final replaces the row and is what history takes);
 *   wired  the CLOSED line is `fuse_caption(stream, refined)` from the REAL core
 *          (`_main/fusion-wire-oracle.py --pair`, i.e. `worker/fusion.py`), the
 *          text the shell's `_fusion_caption` hands to BOTH surfaces.
 *
 * The pair is chosen so the STABILITY RULE changes the text: the finisher drops
 * a word the stream had already put on screen ("agora"). `_diff_ops` never emits
 * `delete`, so the fused line KEEPS it -- the owner does not lose words he has
 * read -- and the two arms' transcript hashes differ for exactly that reason.
 *
 * Prints, per arm: the live row after the partial and after the close, the
 * history commits with their route/producer, and the sha256 of the committed
 * transcript. Exit 0 = measured; 2 = the probe itself failed.
 *
 * Usage: node _main/_fusion-wire-two-arm.js
 */

const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const REPO = path.resolve(__dirname, '..');
const FORMULATION = require(path.join(REPO, 'app', 'panel', 'caption-formulation.js'));

const STREAM = 'o chotto ta rodando agora';
const REFINED = 'o sotto ta rodando';

function fusedPair() {
  const r = spawnSync(process.env.PYTHON || 'python',
    [path.join(__dirname, 'fusion-wire-oracle.py'), '--pair', STREAM, REFINED],
    { encoding: 'utf8' });
  if (r.status !== 0) {
    throw new Error('fusion-wire-oracle.py --pair rc=' + r.status
      + ' stderr=' + ((r.stderr || '').trim().slice(0, 400)));
  }
  return JSON.parse((r.stdout || '').trim().split(/\r?\n/).pop());
}

const words = (v) => (Array.isArray(v)
  ? v.map((t) => (t && typeof t === 'object' ? t.w : t))
  : []);

function drive(closedText) {
  const commits = [];
  const live = [];
  const engine = FORMULATION.createEngine({
    onCommit: (text, reason, meta) => commits.push({ text, reason, meta }),
    onProvisional: (conf, prov) => {
      live.push(words(conf).concat(words(prov)).join(' '));
    },
  });
  // ONE growing stream line, then the finisher's hypothesis for the SAME span.
  engine.ingest(STREAM, { start: 1, end: 2.5, final: false });
  const livePartial = engine.visible();
  engine.ingest(closedText, { start: 1, end: 2.5, final: true, producer: 'redux' });
  const liveAfterClose = engine.visible();
  engine.flush('end');
  const history = commits.map((c) => c.text).join('\n');
  return {
    livePartial,
    liveAfterClose,
    liveUpdates: live.length,
    commits: commits.length,
    routes: commits.map((c) => (c.meta && c.meta.route) || null),
    producers: commits.map((c) => (c.meta && c.meta.producer) || null),
    history,
    sha256: crypto.createHash('sha256').update(history, 'utf8').digest('hex'),
  };
}

function row(name, arm) {
  console.log(`${name.padEnd(6)} live_partial=${JSON.stringify(arm.livePartial)}`);
  console.log(`${' '.repeat(7)}live_after_close=${JSON.stringify(arm.liveAfterClose)}`);
  console.log(`${' '.repeat(7)}history=${JSON.stringify(arm.history)}`
    + ` commits=${arm.commits} routes=${JSON.stringify(arm.routes)}`
    + ` producers=${JSON.stringify(arm.producers)}`);
  console.log(`${' '.repeat(7)}sha256=${arm.sha256}`);
}

try {
  const fused = fusedPair();
  console.log('pair stream=%s', JSON.stringify(STREAM));
  console.log('     refined=%s', JSON.stringify(REFINED));
  console.log('     fused=%s ops=%s stability=%s',
    JSON.stringify(fused.fused), JSON.stringify(fused.ops), fused.stability);
  console.log();
  const raw = drive(REFINED);
  const wired = drive(fused.fused);
  row('raw', raw);
  row('wired', wired);
  console.log();
  console.log('TWO-ARM sha_equal=%s'
    + ' live_changed=%s history_changed=%s'
    + ' stream_words_kept=%s',
  raw.sha256 === wired.sha256,
  raw.liveAfterClose !== wired.liveAfterClose,
  raw.history !== wired.history,
  wired.history.includes('agora'));
  process.exit(0);
} catch (exc) {
  console.error('TWO-ARM PROBE FAILED: %s', exc && exc.message ? exc.message : exc);
  process.exit(2);
}
