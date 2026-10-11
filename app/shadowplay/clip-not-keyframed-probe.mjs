// TWO ARMS for the ClipNotKeyframed refusal at index.js:149-154.
//
// WHY THIS EXISTS. index.js:148-155 measures the first keyframe of every capture and
// refuses to push a segment whose first IDR is absent or more than one frame late:
//     const firstIdr = this.#encoder.firstKeyframeSec(out);
//     if (firstIdr === null || Math.abs(firstIdr) > KEYFRAME_TOLERANCE_SEC) {
//       throw new ClipNotKeyframed(source, `...`);
//     }
// I had read that guard for three turns and never made it fire. A guard nobody can provoke
// is a guard that has not been shown to be able to say NO, which is the same defect class the
// parse gate had this morning.
//
// WHAT THIS MEASURES. NvencEncoder.firstKeyframeSec() on two clips whose first keyframe is
// known to differ, and the boolean the guard at index.js:149 actually evaluates. It does not
// edit the guard and it does not reach into a private field: the guard's own condition is
// recomputed here from the same two values the guard reads, so a disagreement between this
// printout and the guard's behaviour is visible rather than assumed.
//
// THE ARM THAT MUST FAIL. If BOTH clips returned a first keyframe within tolerance, the
// guard would be unreachable and the whole arm would be theatre. That is the outcome to
// watch for, and it is the reason both clips go through the same call.
import { NvencEncoder, KEYFRAME_TOLERANCE_SEC, CAPTURE_FPS } from "./nvenc.js";

const files = process.argv.slice(2);
if (files.length < 2) {
  console.log("NEED_TWO_FILES");
  process.exit(2);
}
const enc = new NvencEncoder();
console.log(`TOLERANCE_SEC ${KEYFRAME_TOLERANCE_SEC}  CAPTURE_FPS ${CAPTURE_FPS}`);
// The literal condition from index.js:149, evaluated against the measured value.
const REFUSAL_TEST = (firstIdr) => firstIdr === null || Math.abs(firstIdr) > KEYFRAME_TOLERANCE_SEC;

for (const f of files) {
  const firstIdr = enc.firstKeyframeSec(f);
  const wouldRefuse = REFUSAL_TEST(firstIdr);
  console.log(`FILE ${f}`);
  console.log(`  FIRST_IDR_SEC ${firstIdr === null ? "null" : firstIdr}`);
  console.log(`  GUARD_WOULD_REFUSE ${wouldRefuse}`);
}
console.log("DONE");