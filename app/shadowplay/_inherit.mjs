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
  results.push({
    label,
    forced,
    refused: threw !== null,
    files: left.length,
    inherited: threw !== null && left.length === 0,
  });
  console.log(`${label}: forced=${forced} refused=${threw !== null} files_left=${left.length} INHERITED=${threw !== null && left.length === 0}`);
}

// The ring module's caller shape is already covered by the permanent arm in
// save-path.test.mjs. These are the two callers that had never been driven.
// Real signatures read from source: the audio track module persists inside render(),
// the captions module inside sidecar().
arm("audio-track", (path, writer) => {
  const track = new AudioTrack({ rate: 48000, channels: 2, savePath: path });
  track.attach({ frames: 60 }, Buffer.alloc(48000 * 2 * 2, 0x20));
  track.render();
});

arm("captions", (path, writer) => {
  const caps = new CaptionTrack({ clip: { id: "c1" }, savePath: path });
  caps.add("hello", 0);
  caps.sidecar();
});

const inherited = results.filter((r) => r.inherited).length;
console.log(`--- INHERITANCE CENSUS ---`);
console.log(`POPULATION_CALLERS_TESTED: ${results.length}  (ring module covered separately)`);
console.log(`CALLERS_INHERITING_REPAIR: ${inherited} / ${results.length}`);
console.log(`REQUIRED_INHERITED: ${results.length}`);
process.exit(inherited === results.length ? 0 : 1);