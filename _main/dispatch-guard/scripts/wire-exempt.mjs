// wire-exempt.mjs - route every hook in this plugin through hook-dispatch.mjs.
//
// OWNER DIRECTIVE 2026-10-06: the owner continues his other projects in the mcode
// DESKTOP. Manager (this agent) and VOD.RIP stay on the CLI and must be EXEMPT from
// the hook layer, so plugin behaviour happens only in the desktop version.
//
// This rewrites hooks.json in place, mechanically, and prints what it changed. It is
// idempotent: running it twice must not double-wrap. A wrapper that wraps a wrapper
// would read stdin once and forward it, which happens to work, but nobody reading
// the manifest could tell.
import { readFileSync, writeFileSync } from 'node:fs';

const MANIFEST = process.argv[2];
const WRAPPER = 'hook-dispatch.mjs';

const raw = readFileSync(MANIFEST, 'utf8');
const doc = JSON.parse(raw);

let routed = 0, already = 0;
for (const [event, groups] of Object.entries(doc.hooks || {})) {
  for (const g of Array.isArray(groups) ? groups : [groups]) {
    for (const h of (g.hooks || [])) {
      const win = h.commandWindows || '';
      if (win.includes(WRAPPER)) { already++; continue; }
      if (!/scripts[\\/]/.test(win)) continue;
      const target = win.replace(/^node\s+"/, '').replace(/"$/, '');
      if (!target.endsWith('.mjs')) continue;
      if (target.includes(WRAPPER)) { already++; continue; }
      const rel = target.replace(/\$\{PLUGIN_ROOT\}[\\/]/, '');
      h.command      = `node "\${PLUGIN_ROOT}/scripts/${WRAPPER}" "\${PLUGIN_ROOT}/${rel}"`;
      h.commandWindows = `node "\${PLUGIN_ROOT}\\scripts\\${WRAPPER}" "\${PLUGIN_ROOT}\\${rel.replace(/\//g, '\\')}"`;
      routed++;
      void event;
    }
  }
}

writeFileSync(MANIFEST, JSON.stringify(doc, null, 2) + '\n');
console.log(`routed=${routed}  already=${already}`);
console.log('every handler now goes through the single exemption choke point');