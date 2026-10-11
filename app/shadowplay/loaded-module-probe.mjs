// Does the runtime load the replay-ring.js I edited, or a different one?
//
// WHY. I spent a turn claiming the product might be running a duplicate module, and
// retracted it by reading index.js's import line. Reading the import proves which SPECIFIER
// is used. It does not prove which FILE the runtime resolved that specifier to, and those
// are different claims -- the same difference that produced clipsDir/dir, ["f9"]/"f9", and
// reading a filename as a location.
//
// WHAT THIS DOES. import.meta.resolve is the runtime's own answer, from inside a live module,
// to "where did this specifier actually land". That path is hashed here and compared against
// the file I edited by path. If they are the same sha, the runtime and the file are the same
// bytes, and there is nothing between my edit and the running product.
//
// THE ARM THAT WOULD REFUTE IT. If the resolved path is somewhere else, or the shas differ,
// then my edits are not in the module that runs, and every measurement today that went through
// this import is measuring something other than the file I edited. That is the outcome worth
// watching.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ReplayRing, idrAligned, backToNearestIdr, DEFAULT_MINUTES } from "./index.js";

const sha = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");

const resolvedUrl = import.meta.resolve("./replay-ring.js");
const resolvedPath = fileURLToPath(resolvedUrl);
const editedPath = new URL("./replay-ring.js", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

console.log(`WINDOW_UTC ${new Date().toISOString()}`);
console.log(`RESOLVED_BY_RUNTIME ${resolvedPath}`);
console.log(`EDITED_BY_ME        ${editedPath}`);
console.log(`SHA_RUNTIME_FILE    ${sha(resolvedPath)}`);
console.log(`SHA_EDITED_FILE     ${sha(editedPath)}`);
console.log(`SAME_FILE           ${resolvedPath.toLowerCase() === editedPath.toLowerCase()}`);
console.log(`SAME_BYTES          ${sha(resolvedPath) === sha(editedPath)}`);

// And the module is not merely resolvable, it is the one holding behaviour. These three
// symbols come out of index.js's re-export of THIS module, so their presence here means the
// re-export chain is live rather than dead.
console.log(`EXPORTED_FROM_INDEX ReplayRing=${typeof ReplayRing} idrAligned=${typeof idrAligned} backToNearestIdr=${typeof backToNearestIdr} DEFAULT_MINUTES=${DEFAULT_MINUTES}`);
console.log("DONE");