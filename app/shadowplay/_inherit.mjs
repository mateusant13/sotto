// DOES THE f48a030 REPAIR INHERIT? The repair lives inside save(), so every caller
// should inherit it. That is an argument, not a measurement. The ring module is the
// only caller already tested, and the other two real callers - the audio track module
// and the captions module - have never been driven through the failure.
//
// Each arm forces the SAME condition: Array.prototype.push throws on the first push of
// a ledger-shaped element, an object carrying both `route` and `name`. Then it asks
// whether that module's clip directory is empty afterwards.
//
// A note on counting, learned here: scanning for the persistence call also matches the
// word inside COMMENTS. nvenc.js has a comment describing a refused remux leaving a
// clip on disk, and that comment matches. So the "5 call sites" figure includes comment
// occurrences. These arms use the real modules, so comments cannot inflate them.
import { mkdtempSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { SavePath } from "./save-path.js";
import { ClipWriter } from "./clip-writer.js";
import { AudioTrack } from "./audio-track.js";
import { CaptionTrack } from "./captions.js";

const realPush = Array.prototype.push;

// Force bookkeeping to fail inside save(), for one call only.
function withForcedFailure(fn) {
  let forced = 0;
  Array.prototype.push = function (...args) {
    const head = args[0];
    if (forced === 0 && this.length === 0 && head && typeof head === "object" &&
        head !== null && "route" in head && "name" in head) {
      forced++;
      throw new Error("FORCED bookkeeping failure");
    }
    return realPush.apply(this, args);
  };
  let threw = null;
  try {
    fn();
  } catch (e) {
    threw = e && e.message ? e.message : "threw";
  } finally {
    Array.prototype.push = realPush;
  }
  return { threw, forced };
}

const results = [];

function arm(label, buildAndRun) {
  const dir = mkdtempSync(join(tmpdir(), `inherit-${label}-`));
  const writer = new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir });
  const path = new SavePath({ writer });
  const { threw, forced } = withForcedFailure(() => buildAndRun(path, writer));
  const left = readdirSync(dir);
  // THE ARM-FIRED CONDITION IS PART OF THE VERDICT, not decoration beside it. My first
  // census computed `refused && files_left===0`, which is exactly what a path that
  // threw BEFORE reaching save() also satisfies. Two bugs in one instrument: a call
  // that never armed, and a verdict that did not notice.
  const armed = forced === 1;
  const inherited = armed && threw !== null && left.length === 0;
  const verdict = armed ? (inherited ? "INHERITED" : "REPAIR_FAILED")
                        : "NOT_MEASURED_arm_never_fired";
  results.push({ label, armed, inherited, verdict });
  console.log(`${label}: forced=${forced} refused=${threw !== null} files_left=${left.length} ${verdict}`);
}

// WHY THE FIRST VERSION OF THIS PROBE ARMED NOTHING, read from source:
//  audio-track.js:72  if (!Number.isInteger(frames) || frames <= 0) throw RangeError
//    I passed an OBJECT as `frames`, so the range guard threw at line 73 and the call
//    never reached save() at line 82. forced=0, refused=true, files_left=0 - a green
//    line made of three facts that meant the opposite of what the green said.
//    attach() persists DIRECTLY: there is no render() step in between. My first version
//    also called render(), which was never on this path.
//  captions.js:59     if (this.#rows.length === 0) return null
//    sidecar() persists directly too, and only once rows exist.
arm("audio-track", (path) => {
  // audio-track.js:23 refuses an empty sources array IN THE CONSTRUCTOR. That is the
  // real reason the arm never fired in the two previous attempts: the constructor threw
  // before attach() was ever called, so no ledger push happened anywhere.
  const track = new AudioTrack({
    rate: 48000, channels: 2, sources: [Buffer.alloc(2048, 0x20)], savePath: path,
  });
  // frames MUST be a positive integer (line 72); an object throws at line 73.
  track.attach(60, Buffer.alloc(4096, 0x20));
});

arm("captions", (path) => {
  // captions.js:15 requires `clip` to be a STRING. I passed an object, so the
  // constructor threw at line 16 and add() was never reached - forced=0. Same class of
  // probe bug as the audio track's empty `sources`: a wrong argument type tripping a
  // guard before the code under test is even entered.
  const caps = new CaptionTrack({ clip: "c1", savePath: path });
  caps.add("hello", 0);
  caps.sidecar();
});

const inherited = results.filter((r) => r.inherited).length;
const notMeasured = results.filter((r) => !r.armed).length;
console.log(`--- INHERITANCE CENSUS ---`);
console.log(`POPULATION_CALLERS_TESTED: ${results.length}  (ring module covered separately)`);
console.log(`CALLERS_INHERITING_REPAIR: ${inherited} / ${results.length}`);
console.log(`CALLERS_NOT_MEASURED: ${notMeasured} / ${results.length}`);
console.log(`REQUIRED_MEASURED: ${results.length}   REQUIRED_INHERITED: ${results.length}`);
// Exit 0 only when every caller was actually MEASURED and inherited. An unmeasured
// caller is a failure of the instrument, not a pass.
process.exit(inherited === results.length ? 0 : 1);