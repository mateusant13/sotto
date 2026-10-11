// EXERCISE replay-ring.js:278, the delivery-time keyframe check, through the real ring.
//
// WHY THIS EXISTS. The keyframe invariant is checked in three places and I had exercised
// none of them end to end. index.js:148 measures the capture and refuses early;
// replay-ring.js:141 states the ring trusts its caller ON PURPOSE, with the reason that an
// encoder alone knows its IDRs; and replay-ring.js:278, inside instantReplay and BEFORE the
// delivery measurement, re-verifies the STORED clip:
//     this.#assertStoredClipStartsOnKeyframe(source);   // :278
//     #assertStoredClipStartsOnKeyframe(stored) {      // :305-306
//       new NvencEncoder().assertStartsOnKeyframe(stored);
//     }
// :278 was read and never provoked. This drives it through the product's own ring.
//
// THE TWO ARMS, and why the second one is the real test. A segment is pushed with
// keyframe: true -- which the ring believes, by contract -- and the ring cuts and saves it
// exactly as a real delivery would. The positive arm's clip starts on an IDR at pts 0, so
// :278 must pass and the delivery must complete. The negative arm's clip has its first IDR
// at pts 1.0, built with -copyts so the timestamp is preserved rather than renormalised to
// zero. The ring BELIEVES keyframe: true for it, because the contract says it does, and
// :278 is the only thing standing between that belief and a stored clip that cannot open on
// a keyframe. If :278 is real, the negative arm refuses and leaves no file.
//
// WHAT WOULD REFUTE THE CLAIM. If the negative arm DELIVERED, then :278 is decoration and
// the whole three-check chain is one check wearing three hats. That is the outcome worth
// watching, not the one I expect.
import { composeShadowplay } from "./index.js";
import { readFileSync, readdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [goodPath, badPath] = process.argv.slice(2);
if (!goodPath || !badPath) {
  console.log("NEED_TWO_FILES");
  process.exit(2);
}

async function arm(label, clipPath) {
  const dir = mkdtempSync(join(tmpdir(), "sp-278-"));
  const app = composeShadowplay({ dir });
  const bytes = readFileSync(clipPath);
  app.ring.push(bytes, { frames: 60, keyframe: true });
  let outcome = "delivered";
  let message = "";
  try {
    const r = await app.ring.instantReplay();
    message = JSON.stringify(r).slice(0, 90);
  } catch (err) {
    outcome = "REFUSED";
    message = `${err.constructor.name}: ${String(err.message).slice(0, 110)}`;
  }
  const left = readdirSync(dir).filter((f) => f.endsWith(".mp4"));
  console.log(`ARM ${label}`);
  console.log(`  OUTCOME ${outcome}`);
  console.log(`  DETAIL ${message}`);
  console.log(`  FILES_LEFT_AFTER ${left.length}${left.length ? " " + left.join(",") : ""}`);
  try { rmSync(dir, { recursive: true, force: true }); } catch { /* best effort */ }
}

await arm("POSITIVE_first_idr_at_0", goodPath);
await arm("NEGATIVE_first_idr_at_1", badPath);
console.log("DONE");