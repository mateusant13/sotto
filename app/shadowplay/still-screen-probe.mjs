// TWO ARMS: a still clip and a moving clip, through the SAME decision function.
//
// WHY THIS EXISTS. One gate run at WINDOW_UTC 2026-10-11T09:07:05Z recorded
//   compose-probe.mjs FAILED exit 1: deliver() -> THREW Error: instant replay refused:
//     ...0000.mp4 holds 28 contiguous d...
// I concluded -- from a measured equality, not from a reproduction -- that 28 meant the
// screen had been still. That conclusion is still inference. This file turns it into two
// measurements.
//
// WHAT IT CAN AND CANNOT DO. composeShadowplay's source is hardwired to
// nvenc.js:68, "-f", "gdigrab", "-i", source, so I cannot hand the product a still screen
// through its own capture path without opening a real window on this desktop. What decides
// the refusal is frame-accounting.js's contentSufficientToCoverClock, and THAT takes a
// file. So this probes the decision with the two inputs that separate the two hypotheses:
// a clip whose every frame is identical, and a clip whose every frame differs. If the still
// arm yields a small longestUniqueRun and the moving arm a large one, then "28 contiguous
// distinct frames" is what a still screen produces, and my explanation is measured rather
// than argued.
//
// THE ARM THAT MUST FAIL. If the still clip ALSO yielded a long distinct run, then
// distinctness is not what the number tracks, and the whole still-screen explanation is
// wrong. That is the outcome that would refute me, and it is why there are two arms.
import { assessDelivery } from "./frame-accounting.js";

const files = process.argv.slice(2);
if (files.length === 0) {
  console.log("NO_INPUTS");
  process.exit(2);
}
for (const f of files) {
  try {
    const v = await assessDelivery(f, 30, 2);
    console.log(`FILE ${f}`);
    console.log(`  DELIVERED_FRAMES ${v.deliveredFrames}`);
    console.log(`  DISTINCT_FRAMES ${v.distinctFrames}`);
    console.log(`  LONGEST_UNIQUE_RUN ${v.longestUniqueRun}`);
    console.log(`  EXPECTED_FRAMES ${v.expectedFrames}`);
    console.log(`  CONTENT_SUFFICIENT ${v.contentSufficientToCoverClock}`);
  } catch (err) {
    console.log(`FILE ${f}`);
    console.log(`  ASSESS_THREW ${err.message.slice(0, 120)}`);
  }
}
console.log("DONE");