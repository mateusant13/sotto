// FORCE THE WINDOW OPEN. Commit f48a030 added a repair inside save() for the case where
// bookkeeping throws AFTER writeClip() has already put the clip on disk. Up to now I
// have only proven that the repair is INERT - that nothing broke when bookkeeping
// succeeded. That is not the same as proving it WORKS.
//
// This probe forces the exact condition: it arms Array.prototype.push so that the FIRST
// push of a ledger-shaped object throws, then calls save() for real and asks what is on
// disk afterwards.
//
// The discriminator is the shape of the pushed element (an object carrying a `route`
// field), not a counter, so unrelated pushes elsewhere in the process are untouched.
// Without it, the throw would land on the wrong array and the result would be noise.
//
// EXPECTED if the repair works: save() throws, the clips directory is EMPTY.
// EXPECTED if it does not: save() throws and a complete clip remains - which is
// exactly the residue the repair exists to prevent.
import { mkdtempSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { SavePath } from "./save-path.js";
import { ClipWriter } from "./clip-writer.js";

const dir = mkdtempSync(join(tmpdir(), "f48-window-"));
const payload = Buffer.alloc(2048, 0x41);

const realPush = Array.prototype.push;
let armed = false;
let forced = 0;
Array.prototype.push = function (...args) {
  const head = args[0];
  if (armed && this.length === 0 && head && typeof head === "object" &&
      head !== null && "route" in head && "name" in head) {
    armed = false;
    forced++;
    throw new Error("FORCED bookkeeping failure after the bytes were written");
  }
  return realPush.apply(this, args);
};

const writer = new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir });
const path = new SavePath({ writer });

armed = true;
let threw = null;
let returned = null;
try {
  returned = path.save("instant-replay", payload);
} catch (e) {
  threw = e && e.message ? e.message : "threw";
} finally {
  Array.prototype.push = realPush;
}

const files = readdirSync(dir);
let bytes = 0;
for (const n of files) bytes += (await import("node:fs")).statSync(join(dir, n)).size;

console.log(`FORCED_FAILURES: ${forced}`);
console.log(`SAVE_RETURNED: ${returned === null ? "null (refused)" : returned}`);
console.log(`SAVE_THREW: ${threw === null ? "no" : "yes"}`);
console.log(`FILES_AFTER: ${files.length} [${files.join(",")}]`);
console.log(`BYTES_AFTER: ${bytes}`);
console.log(`REQUIRED_FILES_AFTER: 0`);
console.log(`LITERAL_CLEANUP: ${files.length === 0}`);
console.log(`ERROR_IS_MINE_NOT_A_CLEANUP: ${threw !== null && threw.startsWith("FORCED")}`);
console.log(`LEAKED_LEDGER: ${JSON.stringify(path.leaked ? path.leaked() : "NO_ACCESSOR")}`);
console.log(`REQUIRED_LEAKED_LEDGER: []`);

const ok = threw !== null && files.length === 0 && threw.startsWith("FORCED");
console.log(`REPAIR_WORKS: ${ok}`);
process.exit(ok ? 0 : 1);