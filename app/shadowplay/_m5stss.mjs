// BUILDING THE INPUT M5 NEEDS: a valid stream with a WRONG EXTRACTION PATH.
//
// Previous attempts all made the STREAM wrong (strip the IDR, feed 64 zero bytes), and
// the delivery gate refused them too - so they could never isolate the keyframe gate.
// M5 defends a different case: the bitstream is intact and measurable, but the CONTAINER
// does not declare its first sample as a sync sample. That is what happens when footage
// is cut or extracted at the wrong offset, and it is the case the gate exists for.
//
// Construction: take a valid MP4 and rewrite its 'stss' box (the sync-sample table) so
// the first entry is dropped. The mdat and every sample stay byte-identical; only the
// container's claim about where sync samples live changes.
//
// If the delivery gate can still MEASURE this file while the keyframe gate refuses it,
// M5 becomes killable and the gap is real rather than unreachable.
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { execFileSync } from "node:child_process";
import { NvencEncoder } from "./nvenc.js";

const tmp = mkdtempSync(join(tmpdir(), "m5stss-"));
const src = join(tmp, "src.mp4");
execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
  "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "30", src]);

const buf = readFileSync(src);
console.log(`SOURCE_BYTES: ${buf.length}`);

// Walk the box tree far enough to find 'stss'. stss lives inside stbl inside minf
// inside mdia inside trak inside moov, so the search is recursive over container boxes.
const CONTAINERS = new Set(["moov", "trak", "mdia", "minf", "stbl"]);
function findBox(b, start, end, name) {
  let off = start;
  while (off + 8 <= end) {
    let size = b.readUInt32BE(off);
    const type = b.toString("latin1", off + 4, off + 8);
    let hdr = 8;
    if (size === 1) {
      size = Number(b.readBigUInt64BE(off + 8));
      hdr = 16;
    }
    if (size < hdr || off + size > end) return null;
    if (type === name) return { at: off, size, hdr };
    if (CONTAINERS.has(type)) {
      const found = findBox(b, off + hdr, off + size, name);
      if (found) return found;
    }
    off += size;
  }
  return null;
}

const stss = findBox(buf, 0, buf.length, "stss");
if (!stss) {
  console.log("STSS_BOX: absent (stream has no sync-sample table)");
  process.exit(1);
}
const count = buf.readUInt32BE(stss.at + stss.hdr + 4);
console.log(`STSS_BOX: found  SYNC_SAMPLES_DECLARED: ${count}`);

// Repoint the FIRST declared sync sample to a later sample number.
//
// My first attempt REMOVED the entry and decremented the count, which left four orphan
// bytes inside the box: the box's SIZE field still described the original entry count,
// so the demuxer hit 'End of file' and the file stopped being measurable. That was my
// bug, not a property of the container. Changing a VALUE instead of the entry count
// leaves every box size and every byte of mdat untouched, so the only thing that
// changes is WHERE THE CONTAINER SAYS SYNC SAMPLES LIVE.
const mutated = Buffer.from(buf);
const entryOff = stss.at + stss.hdr + 8;
const firstEntry = mutated.readUInt32BE(entryOff);
// The second declared sync sample: the first now claims to be there instead.
const secondEntry = count >= 2 ? mutated.readUInt32BE(entryOff + 4) : firstEntry;
mutated.writeUInt32BE(secondEntry, entryOff);
const out = join(tmp, "no-first-sync.mp4");
writeFileSync(out, mutated);
console.log(`FIRST_SYNC_SAMPLE_WAS: ${firstEntry}`);
console.log(`FIRST_SYNC_SAMPLE_NOW: ${secondEntry}`);
console.log(`SYNC_SAMPLES_DECLARED_UNCHANGED: ${count}`);
console.log(`FILE_BYTES_UNCHANGED: ${buf.length === mutated.length}`);
console.log(`SHARED_PREFIX_BYTES: ${(() => {
  let i = 0;
  while (i < buf.length && buf[i] === mutated[i]) i++;
  return i;
})()}`);

// Does ffprobe still measure it? This is the whole point: the file must remain
// measurable, or the delivery gate refuses it and the keyframe gate is not isolated.
let frames = null;
try {
  frames = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
    "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", out],
    { stdio: ["ignore", "pipe", "pipe"] }).toString().trim();
  console.log(`FFPROBE_FRAME_COUNT: ${frames}`);
} catch (e) {
  console.log(`FFPROBE_FRAME_COUNT: FAILED (${(e.stderr || "").toString().split("\n")[0]})`);
}

// THE KEYFRAME GATE.
let gateThrew = null;
try {
  new NvencEncoder().assertStartsOnKeyframe(out);
  console.log("KEYFRAME_GATE: accepted");
} catch (e) {
  gateThrew = e && e.message ? e.message.split("\n")[0] : "threw";
  console.log(`KEYFRAME_GATE: REFUSED -> ${gateThrew}`);
}

// THE DELIVERY GATE. If it accepts, M5 is isolated and killable.
let deliveryThrew = null;
try {
  const { assessDelivery } = await import("./frame-accounting.js");
  const v = await assessDelivery(out, 30, 2);
  console.log(`DELIVERY_GATE: accepted longestUniqueRun=${v.longestUniqueRun} sufficient=${v.contentSufficientToCoverClock}`);
} catch (e) {
  deliveryThrew = e && e.message ? e.message.split("\n")[0] : "threw";
  console.log(`DELIVERY_GATE: REFUSED -> ${deliveryThrew}`);
}

const measurable = frames !== null && /^\d+$/.test(frames) && parseInt(frames, 10) > 0;
console.log(`STILL_MEASURABLE: ${measurable}`);
console.log(`M5_ISOLABLE: ${gateThrew !== null && deliveryThrew === null}`);
console.log(`INPUT_BUILDABLE: ${measurable}`);