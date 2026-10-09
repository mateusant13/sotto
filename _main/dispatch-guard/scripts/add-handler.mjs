// add-handler.mjs -- add ONE hook handler to the manifest, through the exemption choke
// point, idempotently. Written as a file because inline `node -e` with escaped Windows
// paths breaks the string literal; that is a known landmine, not a surprise.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const GUARD = 'C:\\Users\\Administrador\\.minimax\\plugins\\mcode-dispatch-guard';
const DISPATCHER = join(GUARD, 'scripts', 'hook-dispatch.mjs');
const TARGET = join(GUARD, 'scripts', process.argv[2]);
const EVENT = process.argv[3];
const MANIFEST = process.argv[4];

const doc = JSON.parse(readFileSync(MANIFEST, 'utf8'));
const win = `node "${DISPATCHER}" "${TARGET}"`;
const entry = {
  hooks: [{
    type: 'command',
    command: `node "${DISPATCHER.replace(/\\/g, '/')}" "${TARGET.replace(/\\/g, '/')}"`,
    commandWindows: win,
    timeout: 3,
  }],
};

const bucket = doc.hooks[EVENT] || (doc.hooks[EVENT] = []);
const already = bucket.some((g) => JSON.stringify(g).includes(process.argv[2]));
if (already) {
  console.log(`already present on ${EVENT}; nothing added`);
} else {
  bucket.push(entry);
  writeFileSync(MANIFEST, JSON.stringify(doc, null, 2) + '\n');
  console.log(`added ${process.argv[2]} to ${EVENT}; bucket now ${bucket.length}`);
}