'use strict';
/**
 * probe-20261007-node-twin.js — exercises the REAL Node writer
 * (`app/panel/history-store.js append`) into a throwaway history root and
 * reads the `<!-- … -->` marker back off disk. Parity arm for
 * `_history_provenance`. No window, no audio, no device.
 */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const HERE = __dirname;
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'sotto-twin-'));
process.env.SOTTO_HISTORY_ROOT = TMP;

const store = require(path.join(HERE, '..', 'app', 'panel', 'history-store.js'));

const CASES = [
  ['worker-stamped', { route: 'final', start: 12.34, routeSource: 'worker-stamped', reason: 'hold-timeout' }],
  ['panel-deadline', { route: 'provisional-draft', start: 5.0, routeSource: 'panel-deadline', reason: 'status-change' }],
  ['fallback', { route: 'final', start: null, routeSource: 'fallback', reason: '' }],
  ['unknown-src-live', { route: 'final', start: 1.0, routeSource: 'live', reason: '' }],
  ['absent-src', { route: 'final', start: 1.0, reason: 'hold-timeout' }],
];

function markerOnDisk() {
  const out = [];
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir)) {
      const p = path.join(dir, name);
      if (fs.statSync(p).isDirectory()) { walk(p); continue; }
      const text = fs.readFileSync(p, 'utf8');
      for (const line of text.split('\n')) {
        if (!line) continue;
        const m = line.match(/\s*<!--.*-->\s*$/);
        out.push(m ? m[0].trim() : `(NO-MARKER) ${line}`);
      }
    }
  };
  if (fs.existsSync(TMP)) walk(TMP);
  return out;
}

for (const [name, meta] of CASES) {
  const entry = store.append(`line-${name}`, meta);
  const disk = markerOnDisk();
  const tail = disk.length ? disk[disk.length - 1] : '(NOTHING-WRITTEN)';
  console.log(JSON.stringify({ case: name, in: meta, entry: entry ? 'entry' : null, out: tail }));
  // reset the root between cases so each readback is this case's marker
  fs.rmSync(TMP, { recursive: true, force: true });
  fs.mkdirSync(TMP, { recursive: true });
}

fs.rmSync(TMP, { recursive: true, force: true });
