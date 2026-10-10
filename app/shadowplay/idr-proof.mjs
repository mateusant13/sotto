// Proof that the IDR invariant is real and that the gate can say NO.
//
// POPULATION = 1 real NVENC encode, 1 real remux, 1 constructed clip,
//             1 libx264 clip whose first IDR carries SEI, 1 audio-only input,
//             1 accepted-source clip, 5 negative arms, 4 boundary arms,
//             2 tolerance-derivation arms.
// WINDOW = the stdout below. Every number here comes from ffprobe on a real file.
//
// REBUILT after an independent audit. Three of the old arms could pass for
// reasons unrelated to the invariant; the reasons are recorded at each arm so
// the next reader does not have to rediscover them:
//   1. "first IDR within tolerance" compared against a hardcoded 0.5 while the
//      guard enforced 1/DEFAULT_FPS (0.0167). It could not fail in any reachable
//      state -- remux had already enforced the tighter bound.
//   2. The mid-GOP arm never built a mid-GOP clip. ffmpeg snaps `-c copy` seeks
//      onto the keyframe, so the arm measured a non-zero START PTS, not a clip
//      beginning on a non-IDR. Its comment promised INCONCLUSIVE for exactly
//      this case and never implemented it.
//   3. The cut command's failure was swallowed into a "note", so a stale clip
//      left by a crashed prior run was probed and reported as this run's result.
import { execFileSync } from "node:child_process";
import { statSync, writeFileSync, readFileSync, readdirSync, openSync, closeSync, rmSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { NvencEncoder, ClipNotKeyframed, KEYFRAME_TOLERANCE_SEC, CAPTURE_FPS } from "./nvenc.js";
import { DEFAULT_FPS } from "./stream-probe.js";
// ARM 10-12 drive the PRODUCT route, so they need the product's own writer and
// ring -- not a re-implementation of either.
import { ReplayRing } from "./replay-ring.js";
import { SavePath } from "./save-path.js";
import { ClipWriter } from "./clip-writer.js";

const D = join(tmpdir(), "idr-proof");
// AUDIT FIX: a crashed prior run used to leave its clips here, and this run
// measured them as its own. The directory is removed, not merely reused.
rmSync(D, { recursive: true, force: true });
mkdirSync(D, { recursive: true });

const enc = join(D, "enc.mp4");
const clip = join(D, "clip.mp4");
const cut = join(D, "midgop.mp4");
// The elementary stream that BUILDS cut. It is the file that genuinely begins on
// a non-IDR slice, so ARM 2 measures it directly instead of the container.
const midStream = join(D, "midgop-nonidr.264");
const es = join(D, "stream.264");
const junk = join(D, "notavideo.txt");
const seiSrc = join(D, "sei-libx264.mp4");
const seiOut = join(D, "sei-remux.mp4");
const audioSrc = join(D, "audioonly.m4a");
const audioOut = join(D, "audioonly.mp4");

const say = (s) => process.stdout.write(s + "\n");
let fails = 0;
const inconclusive = [];
const expect = (name, cond, detail) => {
  say(`${cond ? "PASS" : "FAIL"}  ${name}${detail ? "  " + detail : ""}`);
  if (!cond) fails++;
};
// A case the toolchain cannot construct is NOT a pass and NOT a failure. It is
// reported, counted, and leaves a non-zero marker in the exit contract.
const skip = (name, why) => { inconclusive.push(name); say(`INCONCLUSIVE  ${name}  ${why}`); };

say("WINDOW_UTC: " + new Date().toISOString().replace(/\.\d+Z$/, "Z"));

// ---- PREFLIGHT ------------------------------------------------------------
// AUDIT FIX: with ffprobe absent, firstKeyframeSec's catch-all returned null
// and the "non-video is refused" arm PASSED for that reason. A missing tool is
// now a failure of its own, before any arm can lean on it.
let toolsOk = true;
for (const bin of ["ffmpeg", "ffprobe"]) {
  let ok = true;
  try { execFileSync(bin, ["-version"], { stdio: ["ignore", "pipe", "ignore"] }); }
  catch { ok = false; }
  if (!ok) toolsOk = false;
  expect(`toolchain ${bin} is present`, ok);
}

// The SEI arm below is only worth running if this build can actually make a
// first IDR that carries side data. Probed up front: an arm that silently has
// no SEI to find would PASS for the wrong reason -- which is precisely how the
// old proof stayed green while dropping the first keyframe.
let libx264Ok = false;
try {
  const encoders = execFileSync("ffmpeg", ["-hide_banner", "-encoders"],
    { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  libx264Ok = /\blibx264\b/.test(encoders);
} catch { libx264Ok = false; }
say(`preflight: libx264 encoder ${libx264Ok ? "present" : "ABSENT (SEI arm will be INCONCLUSIVE)"}`);

// ---- ARM 1: real encode, real remux, invariant enforced on real bytes ------
let firstIdr = null;
try {
  const e = new NvencEncoder({ preset: "p1", gop: 30 });
  const r = e.captureAndEncode(enc, { seconds: 2, fps: 30, gop: 30 });
  expect("encode produced bytes", r.bytes > 0, `${r.bytes} B in ${r.ms.toFixed(0)} ms`);
  const m = e.remux(enc, clip);
  firstIdr = m.firstIdr;
  expect("remux returned firstIdr", typeof firstIdr === "number", `pts=${firstIdr}`);
  // AUDIT FIX: was `Math.abs(firstIdr) <= 0.5`, which the guard had already
  // made unfailable. It now asserts what the guard's own bound is.
  expect("first IDR within the guard's own bound",
    typeof firstIdr === "number" && Math.abs(firstIdr) <= KEYFRAME_TOLERANCE_SEC,
    `pts=${firstIdr} bound=${KEYFRAME_TOLERANCE_SEC}`);
  expect("clip on disk is non-empty", statSync(clip).size > 0, `${statSync(clip).size} B`);
} catch (err) {
  expect("arm1 happy path", false, err.message);
}

// ---- ARM 2 (NEG): a clip that genuinely begins on a non-IDR ---------------
// WHY THIS ARM WAS INCONCLUSIVE, AND WHY IT IS NOT ANY MORE.
// MEASURED WINDOW_UTC 2026-10-10T19:07Z on this host, before this rewrite:
//   trunc.264      first NAL types = [6,1,6,1,...]   <-- a genuine non-IDR start
//   cut.mp4        24 packets, first = "0.966016,K__" <-- starts on a KEYFRAME
//   packets dropped: 53 -> 24
// ffmpeg's raw-H.264 DEMUXER discards every packet before the first IDR. It is
// not the muxer repairing anything: mp4, matroska, mpegts, avi and a fragmented
// mp4 were each tried from the same input and ALL five returned 24 packets whose
// first packet is a keyframe. So `-c copy` cannot produce a non-IDR start in ANY
// container on this toolchain, and the old arm's `packet=flags` test on cut.mp4
// could only ever report that -- it was asking the wrong question about the
// wrong file, and it skipped instead of testing the guard.
//
// THE FIX IS TO TEST THE FILE THAT ACTUALLY BEGINS ON A NON-IDR. `midStream` is
// built from the same annexb as `cut` -- every parameter set (7/8) and SEI (6)
// is KEPT so the stream is well-formed, and only the first IDR SLICE is
// dropped. Two INDEPENDENT instruments must then agree that it really opens on
// a non-key packet before the arm is allowed to count:
//   1. ffprobe's per-packet flags on the first video packet  (container truth)
//   2. the first VCL NAL type parsed out of the bytes       (bitstream truth)
// If either disagrees, the case was not constructed and the arm skips -- it does
// not report a PASS for a file it could not prove is mid-GOP.
//
// WHAT THE REFUSAL PROVES, STATED PLAINLY SO NOBODY OVER-READS IT. The guard
// refuses this file, but it refuses it through the "no keyframe could be read"
// branch, NOT through the tolerance branch: a raw .264 carries no timestamps, so
// ffprobe prints pts_time = "N/A" and firstKeyframeSec's finite filter drops it.
// The tolerance branch cannot be reached with a non-IDR start on this toolchain
// -- there is no container that will carry one. The tolerance branch IS covered,
// decisively, by ARM 2b below. That limit is stated here rather than hidden
// behind an INCONCLUSIVE.
function nalsOf(file) {
  const buf = readFileSync(file);
  const sc = [];
  for (let i = 0; i + 3 < buf.length; i++) {
    if (buf[i] === 0 && buf[i + 1] === 0 && buf[i + 2] === 1) { sc.push({ p: i, l: 3 }); i += 2; }
    else if (buf[i] === 0 && buf[i + 1] === 0 && buf[i + 2] === 0 && buf[i + 3] === 1) { sc.push({ p: i, l: 4 }); i += 3; }
  }
  return { buf, sc, types: sc.map((s) => buf[s.p + s.l] & 0x1f) };
}

function buildMidGopClip() {
  execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
    "-i", enc, "-c", "copy", "-bsf:v", "h264_mp4toannexb", "-f", "h264", es],
    { stdio: ["ignore", "pipe", "pipe"] });
  const { buf, sc, types } = nalsOf(es);
  const firstIdr = types.findIndex((t) => t === 5);
  if (firstIdr < 0) throw new Error("source elementary stream has no IDR to remove");
  // Keep every parameter set and SEI before the first IDR so the stream stays
  // decodable, then drop the IDR SLICE itself: what remains opens on a non-IDR.
  const keep = [];
  for (let i = 0; i < firstIdr; i++) if ([7, 8, 6].includes(types[i])) keep.push(i);
  if (keep.length === 0) throw new Error("no SPS/PPS/SEI precedes the first IDR");
  const firstNonIdr = types.findIndex((t, i) => t === 1 && i > firstIdr);
  if (firstNonIdr < 0) throw new Error("no non-IDR slice after the first IDR");
  for (let i = firstIdr + 1; i < sc.length; i++) keep.push(i);
  writeFileSync(midStream, Buffer.concat(keep.map((i) =>
    buf.subarray(sc[i].p, i + 1 < sc.length ? sc[i + 1].p : buf.length))));
  // `cut` is still built, because ARM 2b needs a containerised late-start clip.
  execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
    "-f", "h264", "-r", "30", "-i", midStream, "-c", "copy", cut],
    { stdio: ["ignore", "pipe", "pipe"] });
  return `built from stream.264: dropped IDR slice #${firstIdr} of ${sc.length} NALs, kept ${keep.length}`;
}

function firstPacketIsKeyframe(file) {
  const raw = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
    "-show_packets", "-show_entries", "packet=flags", "-of", "csv=p=0", file],
    { encoding: "utf8" });
  const first = raw.split("\n").map((s) => s.trim()).filter(Boolean)[0];
  return { isKey: first.includes("K"), flags: first };
}

if (toolsOk) {
  let built = null, buildErr = null;
  try { built = buildMidGopClip(); } catch (err) { buildErr = err.message; }

  if (buildErr) {
    expect("NEG mid-GOP clip construction", false, buildErr);
  } else {
    // Instrument 1: the container's own per-packet flags.
    let flag = null, flagErr = null;
    try { flag = firstPacketIsKeyframe(midStream); } catch (err) { flagErr = err.message; }
    // Instrument 2: the bitstream, independent of any container metadata.
    let firstVcl = null, vclErr = null;
    try {
      const { types } = nalsOf(midStream);
      const v = types.find((t) => [1, 5].includes(t));
      firstVcl = { type: v, isIdr: v === 5 };
    } catch (err) { vclErr = err.message; }

    if (flagErr || vclErr) {
      expect("NEG mid-GOP precondition: the built stream is measurable", false,
        flagErr ?? vclErr);
    } else if (flag.isKey || firstVcl.isIdr) {
      // Both instruments must agree the stream does NOT open on a keyframe
      // before this arm counts. Reporting PASS here would be the instrument
      // lying in the same direction the old arm did.
      skip("NEG mid-GOP clip is REFUSED",
        `precondition failed: packet flags=${flag.flags} isKey=${flag.isKey}, ` +
        `first VCL NAL type=${firstVcl.type} isIdr=${firstVcl.isIdr}; the stream was not built mid-GOP`);
    } else {
      expect("NEG mid-GOP precondition holds: first packet is non-key in BOTH the container and the bitstream",
        true, `flags=${flag.flags}, first VCL NAL type=${firstVcl.type} (not 5); ${built}`);

      const e3 = new NvencEncoder();
      let threw = null;
      try { e3.assertStartsOnKeyframe(midStream); } catch (err) { threw = err; }
      expect("NEG mid-GOP clip is REFUSED", threw instanceof ClipNotKeyframed,
        `${built}; ${threw ? `code=${threw.code}` : "did not throw"}`);
      // Say WHICH branch refused it, so this arm cannot be over-read as
      // coverage of the tolerance throw. See the block comment above.
      if (threw instanceof ClipNotKeyframed) {
        const viaNull = /no keyframe could be read/.test(threw.message);
        say(`note: refused via the ${viaNull ? "no-readable-keyframe" : "tolerance"} branch ` +
          `(raw .264 carries no pts, so firstKeyframeSec returns null; ARM 2b covers tolerance)`);
      }
    }
  }
}

// ---- ARM 2b (NEG): a clip whose first IDR sits beyond the bound is refused -
// This is the arm that actually exercises the tolerance THROW. It is
// deliberately NOT called a mid-GOP arm: `cut` begins on a keyframe and is
// refused for a late start pts. Before this arm existed, deleting the tolerance
// branch from nvenc.js produced no failing assertion at all.
if (toolsOk) {
  const p = new NvencEncoder();
  const late = p.firstKeyframeSec(cut);
  say(`late-start clip first keyframe pts = ${late}`);
  if (typeof late !== "number") {
    skip("NEG late-start clip is REFUSED", "no readable clip to measure");
  } else if (late <= KEYFRAME_TOLERANCE_SEC) {
    // The constructed offset varies run to run (measured 0.066 .. 0.966 on this
    // host). If it ever lands INSIDE the bound there is no late-start case to
    // test, and reporting that as a failure would be the instrument lying in the
    // other direction. It is INCONCLUSIVE, not FAIL.
    skip("NEG late-start clip is REFUSED",
      `constructed offset pts=${late} is inside the bound ${KEYFRAME_TOLERANCE_SEC}; no late-start case exists`);
  } else {
    let threw = null;
    try { p.assertStartsOnKeyframe(cut); } catch (err) { threw = err; }
    expect("NEG late-start clip is REFUSED", threw instanceof ClipNotKeyframed,
      `pts=${late} > bound=${KEYFRAME_TOLERANCE_SEC}; ${threw ? `code=${threw.code}` : "did not throw"}`);
  }
}

// ---- ARM 3 (NEG): non-video input refused, with the toolchain proven above --
writeFileSync(junk, "this is not a video\n");
const e4 = new NvencEncoder();
let junkErr = null;
try { e4.assertStartsOnKeyframe(junk); } catch (err) { junkErr = err; }
expect("NEG non-video file is REFUSED",
  junkErr instanceof ClipNotKeyframed, junkErr ? `code=${junkErr.code}` : "did not throw");

// ---- ARM 4: the error carries a machine-readable code --------------------
expect("error code is stable", new ClipNotKeyframed("f", "d").code === "ERR_CLIP_NOT_KEYFRAMED");
expect("error name is stable", new ClipNotKeyframed("f", "d").name === "ClipNotKeyframed");

// ---- ARM 5: the bound is derived from the rate IN PLAY, not a literal ------
// AUDIT FIX: a tolerance of 0 -- which would refuse every save, since ffmpeg
// routinely hands back a non-zero start pts -- scored 8/8 exit 0 before.
//
// DEFECT FIX: this arm used to assert `KEYFRAME_TOLERANCE_SEC === 1 / DEFAULT_FPS`.
// That pinned the bound to 1/60 s while this module captures at 30 fps, where one
// real frame is 0.033333 s. The assertion was not merely out of date -- it was
// the thing that CERTIFIED the wrong bound. It is replaced by the invariant that
// is actually true, and it is now strictly stronger: it must equal one frame at
// the capture rate AND must NOT equal one frame at DEFAULT_FPS.
expect("tolerance is exactly one frame at the capture rate this module uses",
  KEYFRAME_TOLERANCE_SEC === 1 / CAPTURE_FPS,
  `tolerance=${KEYFRAME_TOLERANCE_SEC} 1/${CAPTURE_FPS}=${1 / CAPTURE_FPS}`);
expect("the capture rate is the real one, not DEFAULT_FPS",
  CAPTURE_FPS === 30 && CAPTURE_FPS !== DEFAULT_FPS,
  `CAPTURE_FPS=${CAPTURE_FPS} DEFAULT_FPS=${DEFAULT_FPS}`);
expect("tolerance is NOT one frame at DEFAULT_FPS (that bound was 2x too tight)",
  KEYFRAME_TOLERANCE_SEC !== 1 / DEFAULT_FPS,
  `1/${DEFAULT_FPS}=${1 / DEFAULT_FPS} must not be the bound at ${CAPTURE_FPS} fps`);
expect("tolerance stays far below the 0.5 s bound the code removed",
  KEYFRAME_TOLERANCE_SEC > 0 && KEYFRAME_TOLERANCE_SEC < 0.5,
  `tolerance=${KEYFRAME_TOLERANCE_SEC}`);

// ---- ARM 6/7: the tolerance is CONSULTED, and only in one direction --------
// A guard that throws for everything must fail 7; a guard that throws for
// nothing must fail 6. Both used to be invisible.
const probe = new NvencEncoder();
const clipFirst = probe.firstKeyframeSec(clip);
expect("positive sample exists for the boundary arms",
  typeof clipFirst === "number", `clip first IDR=${clipFirst}`);

let strictThrew = null;
try { probe.assertStartsOnKeyframe(clip, 0); } catch (err) { strictThrew = err; }
expect("tolerance=0 on a clip whose IDR is at 0 DOES NOT throw",
  strictThrew === null, strictThrew ? "threw" : "accepted");

let looseThrew = null;
try { probe.assertStartsOnKeyframe(junk, 1000); } catch (err) { looseThrew = err; }
expect("tolerance=1000 on a non-video still refuses (null is refused, not widened away)",
  looseThrew instanceof ClipNotKeyframed, looseThrew ? `code=${looseThrew.code}` : "did not throw");

// ---- ARM 8: a first IDR that CARRIES SEI is accepted ----------------------
// WHY THIS ARM HAD TO EXIST. Every arm above fed the gate h264_nvenc output,
// which carries no side data, so ffprobe printed a bare "0.000000". The parser
// therefore never saw the input that broke it. libx264 writes an x264 SEI on
// its first IDR, so `-of csv=p=0` prints "0.000000," -- a trailing comma with
// nothing after it. Number("0.000000,") is NaN, the finite-filter dropped the
// REAL FIRST KEYFRAME, and pts[0] became the SECOND keyframe.
//
// MEASURED WINDOW_UTC 2026-10-10T18:52:55Z against the pre-fix parser:
//   firstKeyframeSec(libx264 clip) = 1   (true first keyframe is 0.000000)
//   assertStartsOnKeyframe           = THREW ERR_CLIP_NOT_KEYFRAMED
//
// This arm runs the whole SAVE PATH (remux), not the helper alone, because a
// gate that only answers correctly when called by hand is not enforced.
const rawFirstLine = (f) => {
  const raw = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
    "-skip_frame", "nokey", "-show_entries", "frame=pts_time", "-of", "csv=p=0", f],
    { encoding: "utf8" });
  return raw.split("\n").map((s) => s.trim()).filter((s) => s.length > 0)[0] ?? "";
};

if (toolsOk && libx264Ok) {
  let buildErr = null;
  try {
    execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
      "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=4",
      "-c:v", "libx264", "-g", "30", "-pix_fmt", "yuv420p", seiSrc],
      { stdio: ["ignore", "pipe", "pipe"] });
  } catch (err) { buildErr = err.message; }

  if (buildErr) {
    expect("SEI clip construction", false, buildErr);
  } else {
    const line = rawFirstLine(seiSrc);
    const carriesSei = /,$/.test(line);
    if (!carriesSei) {
      // No trailing comma => this build emitted no side data => there is no
      // defect-1 case here. Reporting PASS would be the instrument lying.
      skip("SEI first IDR is ACCEPTED (remux)",
        `libx264 clip's first ffprobe line is ${JSON.stringify(line)}, no side-data comma; this build produced no SEI to test`);
    } else {
      expect("SEI precondition holds: the first IDR really carries side data",
        true, `first ffprobe line = ${JSON.stringify(line)} (trailing comma)`);

      // And it must survive -c copy, or the arm would be testing the remuxed
      // file's clean header rather than the SEI carried on the IDR.
      const e8 = new NvencEncoder();
      let threw = null, m8 = null;
      try { m8 = e8.remux(seiSrc, seiOut); } catch (err) { threw = err; }
      if (threw) {
        expect("SEI first IDR is ACCEPTED (remux)", false,
          `remux THREW ${threw.code}: ${threw.message}`);
      } else {
        // ROBUSTNESS FIX, FOUND BY REFUTATION (MEASURED WINDOW_UTC
        // 2026-10-10T19:14Z). rawFirstLine was called unguarded on seiOut. Under
        // the mutation "remux accepts, then discards instead of renaming" the
        // remux returned without throwing, seiOut did not exist, and this
        // ffprobe call took the WHOLE SUITE DOWN with an uncaught ENOENT -- every
        // arm after ARM 8 never ran and reported nothing at all. A crash here is
        // not a neutral outcome: it is silence, and silence is what a suite is
        // not allowed to produce. A missing output is now a FAIL of the arm that
        // needed it, never the end of the run.
        let outLine = null, outErr = null;
        try { outLine = rawFirstLine(seiOut); } catch (err) { outErr = err.message.split("\n")[0]; }
        expect("SEI survives -c copy, so the arm tested what it claims",
          outErr === null && /,$/.test(outLine),
          outErr ? `remux returned without throwing but ${seiOut} could not be probed: ${outErr}`
                 : `remuxed first ffprobe line = ${JSON.stringify(outLine)}`);
        expect("SEI first IDR is ACCEPTED (remux)", outErr === null && m8.firstIdr === 0,
          `remux accepted, firstIdr=${m8.firstIdr} (must be 0, not the second keyframe)`);
        expect("SEI clip was remuxed, never re-encoded",
          e8.encodeCount() === 0, `encodeCount=${e8.encodeCount()}, identical=${m8.identical}`);
      }
    }
  }
} else {
  skip("SEI first IDR is ACCEPTED (remux)",
    `toolsOk=${toolsOk} libx264=${libx264Ok}`);
}

// ---- ARM 9: remux() ITSELF refuses a bad clip, and leaves nothing behind ---
// ARM 2b calls assertStartsOnKeyframe directly. That proves the helper can say
// NO; it does NOT prove the save-time path does. This arm calls remux() and
// requires the refusal to come out of it, with the same error code.
//
// NOTE ON WHAT THIS ARM CAN AND CANNOT BE. MEASURED WINDOW_UTC
// 2026-10-10T19:05Z on this host: `ffmpeg -i in -c copy out` RE-ANCHORS a
// late-start input. A clip whose first IDR sits at pts 0.500000 comes back out
// of a plain remux at pts 0.000000. So there is NO input reachable on this
// toolchain whose REMUXED OUTPUT starts late, and the tolerance-throw branch
// of assertStartsOnKeyframe is unreachable through remux here. What remains
// reachable is an output with no readable IDR at all, which is what this arm
// builds. Recorded rather than papered over: the gate is enforced on the bytes
// that land, and the bytes that land are re-anchored by ffmpeg itself.
//
// DEFECT THIS ARM NOW COVERS. MEASURED WINDOW_UTC 2026-10-10T19:02:16Z:
//     FAIL  a refused remux leaves no stored clip behind
//           REFUSED BUT G:\Temp\idr-proof\audioonly.mp4 exists on disk
// remux() ran ffmpeg to completion and only then ran the guard, so a refusal
// still handed the caller a playable file at the exact path SavePath.save() had
// already reserved via clip-writer's openSync(..., "wx") and listed as written.
const audioOnlyGood = join(D, "audioonly-good.m4a");
const audioOkOut = join(D, "audioonly-good.mp4");

// Every temp remux() creates is `<dir>/.<stem>.remux-<pid>-<n><ext>`. A refused
// save must leave none of them behind either -- that is the half of the fix the
// old arm could not see, because it only looked at the destination.
//
// SCOPE, WIDENED AFTER REFUTATION (MEASURED WINDOW_UTC 2026-10-10T19:15Z): the
// first version of this scan only looked inside D, so the mutation "write the
// temp somewhere else entirely" left this arm GREEN. The destination directory
// is the only place a rename can be atomic, and this arm now proves the litter
// is absent from there AND from the system temp dir, so a temp written next
// door is caught instead of being invisible.
function tempRemuxLitter() {
  const found = [];
  for (const dir of [D, tmpdir()]) {
    let names = [];
    try { names = readdirSync(dir); } catch { continue; }
    for (const f of names) if (f.includes(".remux-")) found.push(`${dir}\\${f}`);
  }
  return found;
}

if (toolsOk) {
  let buildErr = null;
  try {
    execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
      "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "aac", audioSrc],
      { stdio: ["ignore", "pipe", "pipe"] });
  } catch (err) { buildErr = err.message; }

  if (buildErr) {
    expect("NEG remux refuses a clip with no IDR", false, buildErr);
  } else {
    const e9 = new NvencEncoder();
    let threw = null;
    try { e9.remux(audioSrc, audioOut); } catch (err) { threw = err; }
    expect("NEG remux refuses a clip with no IDR",
      threw instanceof ClipNotKeyframed && threw.code === "ERR_CLIP_NOT_KEYFRAMED",
      threw ? `code=${threw.code}` : "remux ACCEPTED a clip with no readable keyframe");

    // A refusal must leave nothing: not at the destination the caller was about
    // to be handed, and not as a temp sibling.
    if (threw) {
      let destinationExists = true;
      try { destinationExists = statSync(audioOut).size > 0; } catch { destinationExists = false; }
      expect("a refused remux leaves no stored clip behind",
        !destinationExists,
        destinationExists
          ? `REFUSED BUT ${audioOut} exists on disk -- the guard runs AFTER ffmpeg wrote the file`
          : "no output file left on disk");
      const litter = tempRemuxLitter();
      expect("a refused remux leaves no temp file behind",
        litter.length === 0,
        litter.length === 0 ? "no .remux-* siblings" : `left behind: ${litter.join(", ")}`);
      // The refusal must name the path the CALLER asked about, never the
      // module's private temp name.
      expect("the refusal names the caller's path, not an internal temp",
        threw.file === audioOut, `error.file=${threw.file}`);
      // And nothing may be logged as remuxed: the log is what the caller reads
      // back as "these clips exist".
      expect("a refused remux is not recorded in the encoder log",
        !e9.calls.includes("remux"), `calls=[${e9.calls.join(",")}]`);

      // ---- THE REAL CALLER: the name is ALREADY RESERVED ---------------------
      // clip-writer's #claim does closeSync(openSync(path, "wx")) -- it creates a
      // 0-byte file at the destination BEFORE any remux runs, and SavePath lists
      // that name as written. So the production path is a rename OVER an existing
      // file, and on refusal the destination is not empty: it is the caller's own
      // reservation. remux must not delete a file it did not create (freeing a
      // name another writer has already skipped would be its own race), and it
      // must not replace it with clip bytes.
      const reserved = join(D, "reserved.clip.mp4");
      const enc10 = new NvencEncoder();
      let claimErr = null, refused = null;
      try {
        closeSync(openSync(reserved, "wx"));
        try { enc10.remux(audioSrc, reserved); } catch (err) { refused = err; }
      } catch (err) { claimErr = err.message; }

      if (claimErr) {
        expect("a refused remux leaves the caller's reservation alone", false, claimErr);
      } else {
        const leftSize = statSync(reserved).size;
        expect("a refused remux leaves the caller's reservation alone",
          refused instanceof ClipNotKeyframed && leftSize === 0,
          `refusal=${refused ? refused.code : "none"}, reservation left at ${leftSize} B ` +
          "(0 = the caller's own empty claim, untouched; >0 = remux left a clip behind)");
      }
    }

    // ---- THE SUCCESS PATH MUST STILL WORK ----------------------------------
    // A fix that makes the refusal safe by never writing the file would also
    // make every save disappear. This arm is the other half of the same
    // guarantee: the accepted clip is on disk, under its own name, byte for byte
    // what ffmpeg produced.
    //
    // Its source needs an encoder that writes an IDR this host may not have, so
    // it is SKIPPED rather than failed when libx264 is absent: a missing
    // encoder is not evidence about remux.
    let srcErr = null;
    try {
      execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=1",
        "-c:v", libx264Ok ? "libx264" : "h264_nvenc", "-g", "15",
        "-pix_fmt", "yuv420p", audioOnlyGood],
        { stdio: ["ignore", "pipe", "pipe"] });
    } catch (err) { srcErr = err.message; }

    if (srcErr) {
      skip("a successful remux still produces its stored clip",
        `could not build an accepted source clip: ${srcErr.split("\n")[0]}`);
    } else {
      const e10 = new NvencEncoder();
      let m10 = null, okErr = null;
      try { m10 = e10.remux(audioOnlyGood, audioOkOut); } catch (err) { okErr = err; }
      let stored = -1;
      if (!okErr) { try { stored = statSync(audioOkOut).size; } catch { stored = -1; } }
      // DEFECT FIX TO THIS PROOF, FOUND BY REFUTATION (MEASURED WINDOW_UTC
      // 2026-10-10T19:12Z). This arm used to assert only "remux returned an
      // object". Under the mutation "accept, then delete the temp instead of
      // renaming it" it stayed GREEN while the clip was silently discarded --
      // the arm name promised the file exists and the assertion did not check.
      // The existence check is now inside the arm, not delegated to the next one.
      expect("a successful remux still produces its stored clip",
        okErr === null && m10 !== null && stored > 0 && stored === m10.outBytes,
        okErr ? `remux THREW ${okErr.code ?? okErr.message}`
              : `inBytes=${m10.inBytes} outBytes=${m10.outBytes}, ${audioOkOut} = ${stored} B on disk`);
      if (m10) {
        expect("the successful clip starts on a keyframe",
          Math.abs(m10.firstIdr) <= KEYFRAME_TOLERANCE_SEC,
          `firstIdr=${m10.firstIdr} bound=${KEYFRAME_TOLERANCE_SEC}`);
        // NEVER RE-ENCODED, proved by the bytes rather than by intent.
        //
        // DEFECT FIX TO THIS PROOF: this arm used to require
        // `m10.identical === true`, i.e. inBytes === outBytes. That was factually
        // wrong and could never have held: `-c copy` between two containers
        // re-writes the moov, so the FILES differ in size even though no frame
        // was re-encoded (MEASURED WINDOW_UTC 2026-10-10T19:04:48Z:
        // inBytes=11289, outBytes=11281, identical=false -- and the clip is
        // perfectly valid). The property the requirement actually names is that
        // nothing was re-encoded, so this now measures THAT: the video
        // elementary stream pulled back out of both files must be byte-identical.
        // Strictly stronger than the size comparison it replaces -- a size
        // equality could coincide while the video changed, and here it does not
        // even hold.
        const esSrc = join(D, "verify-src.264");
        const esOut = join(D, "verify-out.264");
        let esSame = false, esDetail = "";
        try {
          const pull = (src, dest) => execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
            "-i", src, "-c", "copy", "-bsf:v", "h264_mp4toannexb", "-f", "h264", dest],
            { stdio: ["ignore", "pipe", "pipe"] });
          pull(audioOnlyGood, esSrc);
          pull(audioOkOut, esOut);
          const a = readFileSync(esSrc), b = readFileSync(esOut);
          esSame = a.length === b.length && a.equals(b);
          esDetail = `elementary stream ${a.length} B vs ${b.length} B, byte-identical=${esSame}`;
        } catch (err) { esDetail = `could not pull the elementary stream: ${err.message.split("\n")[0]}`; }
        expect("the successful remux never re-encoded: the video bytes are unchanged",
          e10.encodeCount() === 0 && esSame,
          `encodeCount=${e10.encodeCount()}, ${esDetail}`);
        expect("the successful remux reported both byte counts",
          m10.inBytes > 0 && m10.outBytes > 0 && typeof m10.ms === "number",
          `inBytes=${m10.inBytes} outBytes=${m10.outBytes} identical=${m10.identical} (container sizes may differ; the video bytes above must not)`);
        expect("the successful remux is recorded in the encoder log",
          e10.calls.filter((c) => c === "remux").length === 1,
          `calls=[${e10.calls.join(",")}]`);
        const litter2 = tempRemuxLitter();
        expect("a successful remux leaves no temp file behind",
          litter2.length === 0,
          litter2.length === 0 ? "no .remux-* siblings" : `left behind: ${litter2.join(", ")}`);
      }
    }
  }
}

// ---- ARM 10: THE REAL SAVE ROUTE, END TO END ------------------------------
// WHY THIS ARM HAD TO BE WRITTEN FROM SCRATCH. Every arm above reaches
// NvencEncoder directly. ARM 9 calls remux(), but remux() has ZERO call sites in
// the product (grep `.remux(` over every .js in this directory, WINDOW_UTC
// 2026-10-10T18:55Z), so an arm that proves remux() refuses proves a gate that
// nothing reaches. The route that DOES run on every F9 press is
// ReplayRing.instantReplay() -> SavePath.save() -> ClipWriter.nextClipName().
// This arm drives that route, not the gate.
//
// WHAT IS REAL HERE. ReplayRing, SavePath, ClipWriter, NvencEncoder's gate and
// the delivery gate are the product modules, unstubbed. The clip is produced by
// real ffmpeg and measured by real ffprobe. The ONLY substitution is the writer's
// byte-production, and it is labelled as such at each arm -- because the product
// genuinely lacks that step, which is the finding, not a convenience.
const ringDir = join(D, "realsave");
mkdirSync(ringDir, { recursive: true });
const realClip = join(ringDir, "real-src.mp4");

// A writer that reserves the name the way ClipWriter does and then puts REAL
// ENCODED BYTES at that path. This stands in for the step the product does not
// have: save() reserves a name and writes no bytes, so on the real route the file
// is a 0-byte placeholder (ARM 11 measures exactly that). Everything downstream
// of the write -- pathOf, the keyframe gate, the delivery gate -- is the product's.
class ByteProducingWriter {
  #n = 0;
  constructor(dir, bytes) { this.dir = dir; this.bytes = bytes; this.log = []; }
  nextClipName() {
    const name = `${String(this.#n++).padStart(4, "0")}.mp4`;
    writeFileSync(join(this.dir, name), this.bytes);
    this.log.push(name);
    return name;
  }
  pathFor(name) { return join(this.dir, name); }
}

let realSrcBytes = null, srcBuildErr = null;
try {
  execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
    "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=3",
    "-c:v", libx264Ok ? "libx264" : "h264_nvenc", "-g", "30",
    "-pix_fmt", "yuv420p", realClip], { stdio: ["ignore", "pipe", "pipe"] });
  realSrcBytes = readFileSync(realClip);
} catch (err) { srcBuildErr = err.message; }

if (!toolsOk) {
  skip("REAL ROUTE: a real encoded clip is ACCEPTED through ReplayRing.instantReplay",
    "ffmpeg/ffprobe absent");
} else if (srcBuildErr) {
  skip("REAL ROUTE: a real encoded clip is ACCEPTED through ReplayRing.instantReplay",
    `could not build a real source clip: ${srcBuildErr.split("\n")[0]}`);
} else {
  // minutes is set so the ring's own clock budget matches the 3 s clip: at 30 fps
  // a 3 s clip is 90 frame slots, and testsrc is unique per frame, so the
  // DELIVERY gate can also pass. That is deliberate -- it means this arm proves
  // the whole route goes GREEN on good input, not merely that it refuses loudly.
  const w = new ByteProducingWriter(ringDir, realSrcBytes);
  const ring = new ReplayRing({ minutes: 0.05, fps: 30, gopSize: 30, savePath: new SavePath({ writer: w }) });

  let r10 = null, e10b = null;
  try { r10 = await ring.instantReplay(); } catch (err) { e10b = err; }

  expect("REAL ROUTE precondition: the bytes handed to the writer are a real keyframed clip",
    realSrcBytes.length > 0, `${realSrcBytes.length} B from real ffmpeg`);

  expect("REAL ROUTE: instantReplay ACCEPTS a real clip that begins on a keyframe",
    e10b === null && r10 !== null,
    e10b ? `refused with ${e10b.code ?? e10b.name}: ${e10b.message}` : `name=${r10.name}`);

  if (r10) {
    // The stored path must be the one the writer reserved, and must hold bytes.
    expect("REAL ROUTE: the stored clip is the file the gate measured",
      r10.path === join(ringDir, r10.name) && statSync(r10.path).size > 0,
      `${r10.path} = ${statSync(r10.path).size} B (source was ${realSrcBytes.length} B)`);

    // And the gate must have actually run on that path, not merely been reachable.
    const gateSawIt = new NvencEncoder().firstKeyframeSec(r10.path);
    expect("REAL ROUTE: the keyframe gate read the stored clip it accepted",
      typeof gateSawIt === "number" && Math.abs(gateSawIt) <= KEYFRAME_TOLERANCE_SEC,
      `first IDR pts=${gateSawIt} bound=${KEYFRAME_TOLERANCE_SEC}`);

    // Proof the route ran END TO END rather than stopping at the gate.
    expect("REAL ROUTE: the delivery gate also ran and returned a verdict",
      r10.verdict !== null && typeof r10.verdict.longestUniqueRun === "number",
      `longestUniqueRun=${r10.verdict?.longestUniqueRun} expectedFrames=${r10.verdict?.expectedFrames}`);

    // The discriminator that makes ARM 11 meaningful: on a GOOD clip the route
    // returns, and on a BAD one it must refuse. If both behaved identically, the
    // gate would be doing nothing and ARM 11 would prove nothing.
    expect("REAL ROUTE: a good clip is not refused with the keyframe error",
      e10b === null, e10b ? `unexpected refusal: ${e10b.message}` : "accepted, as required");
  }

  // ---- ARM 11 (NEG): the REAL route refuses a clip with no keyframe ---------
  // This is the defect, measured through the route rather than through the gate.
  // No stub, no injected bytes: the real SavePath + real ClipWriter reserve the
  // name exactly as the product does, and save() writes nothing. The file that
  // reaches the gate is the 0-byte placeholder the product actually produces.
  const bareDir = join(D, "realsave-bare");
  mkdirSync(bareDir, { recursive: true });
  const bareWriter = new ClipWriter({
    exists: (n) => readdirSync(bareDir).includes(n),
    dir: bareDir,
  });
  const barePath = new SavePath({ writer: bareWriter });
  const bareRing = new ReplayRing({ minutes: 0.05, fps: 30, gopSize: 30, savePath: barePath });

  let e11 = null, r11 = null;
  try { r11 = await bareRing.instantReplay(); } catch (err) { e11 = err; }

  expect("NEG REAL ROUTE: a stored clip with no keyframe is REFUSED by the route itself",
    e11 instanceof ClipNotKeyframed && e11.code === "ERR_CLIP_NOT_KEYFRAMED",
    e11 ? `code=${e11.code} :: ${e11.message}` : "the route ACCEPTED a 0-byte clip");

  expect("NEG REAL ROUTE: the refusal names the stored clip by its FULL path",
    e11 instanceof Error && e11.file === join(bareDir, "0000.mp4"),
    e11 ? `error.file=${e11.file}` : "no error to inspect");

  // THE SPECIFIC DEFECT THIS FIXES, AS AN ASSERTION. Before this change the same
  // route refused the same 0-byte file, but ffprobe ran FIRST and the throw was
  // rewritten as "could not measure delivery" -- a measurement failure that hid a
  // keyframe failure. This arm fails on the old code and passes on the new.
  expect("NEG REAL ROUTE: the refusal names the KEYFRAME, not a masked measurement",
    e11 instanceof Error && !/could not measure delivery/.test(e11.message),
    e11 ? `message=${JSON.stringify(e11.message.slice(0, 90))}` : "no error");

  expect("NEG REAL ROUTE: the route refused BEFORE the delivery gate could mask it",
    e11 instanceof ClipNotKeyframed,
    e11 ? "ClipNotKeyframed reached the caller unchanged (not re-wrapped)" : "no error");
}

// ---- ARM 12: remux() still has no product callers --------------------------
// Stated as an assertion so the report cannot drift from the code. If a future
// lane wires remux() into the save path, this arm goes red and the report must be
// rewritten -- at that point the single call site above would no longer be the
// only writer of the invariant.
if (toolsOk) {
  let callers = [];
  const here = new URL(".", import.meta.url);
  for (const f of readdirSync(here)) {
    if (!f.endsWith(".js")) continue;
    if (f === "nvenc.js" || f === "encoder.js") continue;   // the definitions themselves
    // Comments are stripped BEFORE counting, because this very file's own
    // documentation names `remux()` while explaining that nothing calls it. A
    // scanner that counted prose would report a caller that does not exist --
    // which is the same class of error as the grep that motivated this task:
    // a non-zero count that proves nothing about reachability.
    const body = readFileSync(new URL(f, here), "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, " ")          // block comments
      .replace(/(^|[^:])\/\/.*$/gm, "$1");       // line comments, keeping ':' out of URLs
    if (/\bremux\s*\(/.test(body)) callers.push(f);
  }
  expect("remux() has no product callers outside its own definition",
    callers.length === 0,
    callers.length === 0
      ? "0 of the product .js files call remux() (comments excluded)"
      : `called from: ${callers.join(", ")}`);
}
say(`INCONCLUSIVE_COUNT: ${inconclusive.length}${inconclusive.length ? "  " + inconclusive.join("; ") : ""}`);
// AUDIT FIX: cleanup used to run before the report and destroy the evidence of
// a red run, while leaving the directory itself behind. Green cleans up; red
// keeps everything and says where it is.
if (fails === 0 && inconclusive.length === 0) {
  rmSync(D, { recursive: true, force: true });
  say("cleanup: removed (green)");
} else {
  say(`cleanup: PRESERVED at ${D} (${fails} fails, ${inconclusive.length} inconclusive)`);
}
say(`FAILS: ${fails}`);
process.exitCode = fails === 0 && inconclusive.length === 0 ? 0 : 1;