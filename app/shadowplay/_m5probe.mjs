// CAN M5 BE KILLED? - build an input that the KEYFRAME gate must refuse and that the
// SUFFICIENCY gate would otherwise accept.
//
// 64 zero bytes cannot kill M5: they are undecodable, so the delivery-measurement gate
// refuses them too, and disabling the keyframe gate changes nothing observable. The
// input M5 needs is a clip ffprobe CAN measure, with enough distinct content to pass
// sufficiency, whose first frame is not a keyframe.
//
// Construction: Annex-B surgery. Keep SPS, PPS and every non-IDR picture. That is a
// stream whose first picture is a P-frame. My earlier probe proved such a stream has 0
// DECODABLE frames; the question here is narrower and prior: does the product's keyframe
// gate reject it, and does the delivery gate find nothing to complain about?
//
// Every line here is MEASURED. If the input cannot be built, this says so and claims
// nothing either way, which is what happened for the non-IDR arm.
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { execFileSync } from "node:child_process";
import { NvencEncoder } from "./nvenc.js";

const tmp = mkdtempSync(join(tmpdir(), "m5probe-"));
const src = join(tmp, "src.h264");
execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
  "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "30", "-f", "h264", src]);

const buf = readFileSync(src);
// Locate Annex-B start codes and the ORIGINAL index of each NAL.
const starts = [];
for (let i = 0; i < buf.length - 3; i++) {
  if (buf[i] === 0 && buf[i + 1] === 0 && buf[i + 2] === 1) {
    const four = i > 0 && buf[i - 1] === 0;
    starts.push({ at: i - (four ? 1 : 0), type: buf[i + 3] & 0x1f });
    i += 2;
  }
}
const origIndex = new Map(starts.map((s, k) => [s, k]));
console.log(`NAL_UNITS: ${starts.length}`);
console.log(`IDR_COUNT: ${starts.filter((s) => s.type === 5).length}`);

// Keep SPS(7), PPS(8), SEI(6) and pictures that are NOT IDR. Bound each kept slice by
// the NEXT NAL IN THE ORIGINAL LIST, never the next kept one - that mistake silently
// re-absorbed the IDR bytes on an earlier attempt and produced a false reading.
const parts = [];
for (const s of starts) {
  if (s.type === 5) continue;
  const i = origIndex.get(s);
  const to = i + 1 < starts.length ? starts[i + 1].at : buf.length;
  parts.push(buf.subarray(s.at, to));
}
const midGop = Buffer.concat(parts);
const out = join(tmp, "midgop.h264");
writeFileSync(out, midGop);
console.log(`BYTES_RETAINED_PCT: ${(100 * midGop.length / buf.length).toFixed(1)}`);

// What does ffprobe see? It may report frames it cannot display.
let flags = "";
try {
  flags = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
    "-show_entries", "frame=key_frame", "-of", "csv=p=0", out],
    { stdio: ["ignore", "pipe", "pipe"] }).toString().trim();
} catch (e) {
  flags = "PROBE_FAILED";
}
const list = flags.split("\n").map((s) => s.trim()).filter((s) => /^\d+$/.test(s));
console.log(`PROBE_FRAMES_LISTED: ${list.length}`);
console.log(`FIRST_KEY_FRAME_FLAG: ${list.length ? list[0] : "UNKNOWN"}`);

// THE MEASUREMENT THAT MATTERS: does the product's keyframe gate refuse this?
let gateThrew = null;
try {
  new NvencEncoder().assertStartsOnKeyframe(out);
  console.log(`KEYFRAME_GATE: accepted`);
} catch (e) {
  gateThrew = e && e.message ? e.message.split("\n")[0] : "threw";
  console.log(`KEYFRAME_GATE: REFUSED -> ${gateThrew}`);
}

// And does the DELIVERY gate have anything to say? If it does not, this input isolates
// the keyframe gate and M5 becomes killable.
let deliveryThrew = null;
let longest = null;
try {
  const { assessDelivery } = await import("./frame-accounting.js");
  const v = await assessDelivery(out, 30, 2);
  longest = v.longestUniqueRun;
  console.log(`DELIVERY_GATE: accepted longestUniqueRun=${longest} sufficient=${v.contentSufficientToCoverClock}`);
} catch (e) {
  deliveryThrew = e && e.message ? e.message.split("\n")[0] : "threw";
  console.log(`DELIVERY_GATE: REFUSED -> ${deliveryThrew}`);
}

const isolable = gateThrew !== null && deliveryThrew === null;
console.log(`M5_ISOLABLE: ${isolable}`);
console.log(`INPUT_BUILDABLE: ${list.length > 0 && list[0] === "0"}`);