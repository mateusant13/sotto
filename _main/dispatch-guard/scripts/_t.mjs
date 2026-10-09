import { readFileSync } from 'node:fs';
const d=readFileSync(0,'utf8');
process.stdout.write('HANDLER_RAN');
