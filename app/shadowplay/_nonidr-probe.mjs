// IS A NON-IDR-FIRST H.264 STREAM EVEN CONSTRUCTIBLE?
//
// Five prior attempts failed to build the negative arm "a valid container whose first
// frame is not a keyframe" (mine 3, the reviewer's 2). Every one produced a file ffprobe
// could not decode. This asks the prior question instead of attempting a sixth:
// can such a stream EXIST as a decodable input?
//
// The claim being tested: in H.264 the first picture NAL must be an IDR, so an input
// whose first frame is a non-keyframe is not merely hard to build -- it is not a
// decodable file at all. If true, the negative arm is unreachable and the instrument's
// gap is a construction problem, not a hole in the gate.
//
// Method: split Annex-B into NALs by start code, drop every type-5 (IDR), rejoin the
// rest, and ask ffprobe how many frames it can decode. Then remux to MP4 and ask again.
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

const src = process.argv[2];
const buf = readFileSync(src);

// Locate Annex-B start codes: 00 00 01 (3-byte) or 00 00 00 01 (4-byte).
const starts = [];
for (let i = 0; i < buf.length - 3; i++) {
  if (buf[i] === 0 && buf[i + 1] === 0 && buf[i + 2] === 1) {
    const four = i > 0 && buf[i - 1] === 0;
    starts.push({ at: i - (four ? 1 : 0), type: buf[i + 3] & 0x1f });
    i += 2;
  }
}
const order = starts.map((s) => s.type);
console.log(`NAL_UNITS_PARSED: ${order.length}`);
console.log(`FIRST_PICTURE_NAL_TYPE: ${order.find((t) => t === 1 || t === 5)}`);
console.log(`IDR_COUNT: ${order.filter((t) => t === 5).length}`);

// Keep every NAL that is NOT an IDR: SPS, PPS, SEI and the P-frames.
//
// A NAL's bytes run from ITS OWN start code to the NEXT start code. My first attempt
// re-emitted only the 4-byte start prefix and threw away every NAL's payload: it
// produced 256 bytes from a 14527-byte stream and would have "proved" anything at all.
// Each kept slice is taken as [start, nextStart). The retained-payload percentage is
// printed so a broken reconstruction can never again be read as a property of H.264.
const kept = starts.filter((s) => s.type !== 5);
const totalBytes = buf.length;
console.log(`NALS_KEPT: ${kept.length}`);

// A NAL's bytes run from ITS OWN start code to the NEXT start code -- and "next" must
// mean next in the ORIGINAL list, not next among the kept ones. Bounding each kept
// slice by the next KEPT entry re-absorbs the removed IDR's bytes into the preceding
// slice: the result retained 14527 of 14527 bytes, i.e. no IDR was actually removed and
// the "decodes fine" reading measured a stream that still had its IDRs. Index the
// ORIGINAL list for the bound.
const parts = [];
for (const s of kept) {
  const i = starts.indexOf(s);
  const to = i + 1 < starts.length ? starts[i + 1].at : buf.length;
  parts.push(buf.subarray(s.at, to));
}
let out = Buffer.concat(parts);
const noIdr = "G:\\Temp\\no-idr.h264";
writeFileSync(noIdr, out);
console.log(`STRIPPED_BYTES: ${out.length} of ${totalBytes}`);
const idrBytes = totalBytes - out.length;
console.log(`IDR_BYTES_REMOVED: ${idrBytes}`);
console.log(`PAYLOAD_RETAINED_PCT: ${(100 * out.length / totalBytes).toFixed(1)}`);

// THE MEASUREMENT: how many frames can a decoder recover from a stream with no IDR?
let frames = 0;
let stderr = "";
try {
  const o = execFileSync("ffprobe",
    ["-v", "error", "-select_streams", "v:0", "-count_frames",
     "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", noIdr],
    { stdio: ["ignore", "pipe", "pipe"] }).toString().trim();
  frames = parseInt(o, 10) || 0;
  console.log(`DECODABLE_FRAMES_NO_IDR: ${frames}`);
} catch (e) {
  stderr = (e.stderr ? e.stderr.toString() : "").trim().split("\n")[0];
  console.log(`DECODABLE_FRAMES_NO_IDR: 0`);
  console.log(`FFPROBE_ERROR: ${stderr}`);
}

// Control: the SAME stream with its IDRs intact, so the zero above is attributable to
// the removal and not to a broken extraction.
let controlFrames = 0;
try {
  const o = execFileSync("ffprobe",
    ["-v", "error", "-select_streams", "v:0", "-count_frames",
     "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", src],
    { stdio: ["ignore", "pipe", "pipe"] }).toString().trim();
  controlFrames = parseInt(o, 10) || 0;
  console.log(`DECODABLE_FRAMES_WITH_IDR_CONTROL: ${controlFrames}`);
} catch (e) {
  console.log(`DECODABLE_FRAMES_WITH_IDR_CONTROL: probe failed`);
}

const unreachable = frames === 0 && controlFrames > 0;
console.log(`NON_IDR_FIRST_STREAM_IS_UNDECODABLE: ${unreachable}`);
console.log(`NEGATIVE_ARM_REACHABLE: ${!unreachable}`);