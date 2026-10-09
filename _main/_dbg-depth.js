// Throwaway: report the brace/paren depth per line of a JS file, ignoring
// strings and comments, to find an unbalanced bracket.
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
let out = '';
let i = 0;
let state = null;
const n = src.length;
while (i < n) {
  const c = src[i];
  const c2 = src.slice(i, i + 2);
  if (state === null) {
    if (c2 === '//') { state = 'line'; i += 2; continue; }
    if (c2 === '/*') { state = 'block'; i += 2; continue; }
    if (c === "'" || c === '"') { state = c; i += 1; continue; }
    out += c; i += 1; continue;
  }
  if (state === 'line') { if (c === '\n') { state = null; out += '\n'; } i += 1; continue; }
  if (state === 'block') { if (c2 === '*/') { state = null; i += 2; } else { if (c === '\n') out += '\n'; i += 1; } continue; }
  if (c === '\\') { i += 2; continue; }
  if (c === state) state = null;
  i += 1;
}
const lines = out.split('\n');
let d = 0;
let p = 0;
lines.forEach((ln, k) => {
  for (const ch of ln) {
    if (ch === '{') d += 1; else if (ch === '}') d -= 1;
    else if (ch === '(') p += 1; else if (ch === ')') p -= 1;
  }
  if (process.argv[3] && k + 1 >= Number(process.argv[3]) && k + 1 <= Number(process.argv[4])) {
    console.log((k + 1) + '  {=' + d + ' (=' + p + '   ' + ln.trim().slice(0, 70));
  }
});
console.log('FINAL depth braces=' + d + ' parens=' + p + ' (0 is balanced)');
