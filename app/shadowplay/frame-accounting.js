// Did the clip actually cover the clock it claims to cover?
//
// A file that exists, has a plausible duration and a plausible byte size can
// still be a lie: a frozen display encoded at 60 fps produces a "10 second"
// clip in which half the frames are exact copies of their neighbour and the
// last two seconds are a single still image repeated. Every coarse metric says
// fine. The only question that matters is whether enough DISTINCT CONSECUTIVE
// content exists to stand in for the wall time.
//
// MEASURED on this host, WINDOW_UTC 2026-10-10T13:46:02Z, over a population of
// 13 .js files in app/shadowplay (ESM 13, CJS 0):
//   ffprobe -v error -select_streams v:0 -count_frames
//            -show_entries stream=nb_read_frames -of csv=p=0 out.mp4
//   -> stdout is "150\r\n" (HEX dump of the captured pipe: 31 35 30 0D 0A).
//
// THE BUG THIS FILE EXISTS TO AVOID -- measured, not theoretical:
//   "150\r\n".split("\n").pop()  === ""          (length 0)
//   Number("")                  === 0
//   Number.isFinite(0)           === true
// So the naive "last line of ffprobe output" parse returns 0 frames for a file
// that has 150 of them, and 0 is the exact value every caller interprets as
// "zero frames were delivered". A parse failure and a real measurement are
// then indistinguishable. Every parse below therefore rejects empty and
// non-numeric input instead of coercing it to 0. countFrames THROWS rather
// than guessing; a caller that wants a number is entitled to know it is a number.
//
// A PERCENTAGE ALONE IS NOT ENOUGH, and this is the second reason the file
// exists. A distinct-content percentage counts unique frames ANYWHERE in the
// file, so a clip can be mostly unique overall and still be dead solid for
// most of its length. A transcriber does not care that some frame somewhere
// was new; it cares whether the picture kept changing while the words were
// being spoken.
//
// MEASURED on this host, WINDOW_UTC 2026-10-10T14:0x, reproducible from:
//
//   ffmpeg -f lavfi -i testsrc=size=640x360:rate=30:duration=5 -r 60 \
//          -c:v libx264 -qp 0 dup60.mp4
//   assessDelivery("dup60.mp4", 60, 5) ->
//     deliveredFrames 300, distinctFrames 150,
//     coverage 0.5, contiguousRatio 0.006667,
//     contentSufficientToCoverClock FALSE
//
// FIFTY PERCENT distinct, and it is still a lie: the 30 fps source was written
// into a 60 fps container, so every real picture is stored twice and the longest
// stretch of new content is 2 frames out of an expected 300. The distinct
// percentage says "half this clip is unique"; the contiguous percentage says
// "this clip contains two frames of information and then stops".
// (-qp 0 keeps the duplicates bit-identical. Re-encoded with h264_nvenc the
// same clip measured 297 distinct of 300 -- lossy rate control makes nominally
// identical frames decode differently, so frame hashing sees noise. That is a
// real caveat on this whole approach, not a bug in it.)
//
// The team's cited measurement on this host is one clip at 85.1% distinct
// against only 20.8% contiguous -- the same shape, less extreme. Both numbers
// are reported side by side below and the verdict is taken from the contiguous
// one.
import { execFile } from "node:child_process";
import { statSync } from "node:fs";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

// -- constants -------------------------------------------------------------
// Every embedded literal lives here with the reason for its value. There are no
// inline magic numbers in the logic below.

const FFPROBE_BIN = "ffprobe";
// Bare name, resolved through PATH, for the same reason nvenc.js calls the bare
// name: the installed toolchain is not vendored and the repo has no dependency
// on where it lands.

const FFMPEG_BIN = "ffmpeg";
// Same rationale as FFPROBE_BIN.

const LOGLEVEL_ARGS = ["-v", "error"];
// Shared by both tools. error, not warning/info: the banner and the progress
// meter are noise we do not parse, and raising the threshold does not suppress
// the diagnostics we DO care about -- corrupt-frame and dropped-frame messages
// are printed at error level, and runTool preserves stderr either way.
const VIDEO_STREAM_SELECTOR = "v:0";
// The first video stream. Accounting for the audio stream would report frames
// that carry no picture, which is precisely the conflation this module exists
// to avoid.
const CSV_NO_HEADER_FORMAT = ["-of", "csv=p=0"];
// csv=p=0, not ffprobe's default key=value: the default output shape changes
// between ffprobe builds while csv=p=0 is one bare field per line, which is
// what makes the strict parse below possible.
const COUNT_FRAMES_ARGS = [
  ...LOGLEVEL_ARGS, "-select_streams", VIDEO_STREAM_SELECTOR,
  "-count_frames", "-show_entries", "stream=nb_read_frames",
  ...CSV_NO_HEADER_FORMAT,
];
// The exact argument vector MEASURED against this host's ffprobe above.
const NB_READ_FRAMES_FIELD = "nb_read_frames";
// The single stream field ffprobe populates under -count_frames. It is the
// count of frames actually READ, not nb_frames, which is only a container
// hint and is routinely wrong for a stream that was cut or remuxed. Named so
// the show_entries key is not a string buried in the middle of a literal.

const FRAMEMD5_HASH = "md5";
// md5, not sha256: this compares hashes for EQUALITY to detect duplicate
// frames and never uses them as a digest of record, so collision resistance is
// irrelevant and md5 is the faster of the two framemd5 hashers.
const FRAMEMD5_INPUT_FLAG = "-i";
// The input is a real path passed as the argument after this flag. ffmpeg then
// has exactly one input and knows which one it is. This flag and the path must
// sit in the MIDDLE of the vector -- before the output flags -- which is why
// the args below are split into an input half and an output half rather than
// being one flat list with the path appended.
const FRAMEMD5_OUTPUT_ARGS = [
  "-an", "-f", "framemd5", "-hash", FRAMEMD5_HASH, "-",
];
// -an drops audio: we are accounting for picture content and audio lines would
// otherwise interleave into the hash stream. - (stdout) instead of a file so
// nothing is written to disk next to the clip being measured.
const FRAMEMD5_LAST_FIELD = -1;
// framemd5 rows end with the checksum as the final comma-separated field:
// "0, 149, 149, 1, 691200, 18fc6e...". Measured line above. Taking the last
// field rather than a fixed column survives the stream/layout columns that
// differ between builds.

const FRAMEMD5_COMMENT_PREFIX = "#";
// Header rows ("#format:", "#version:", "#hash:") are not frames and must be
// dropped BEFORE any field is read.

const RUN_LENGTH_ON_REPEAT = 0;
// A hash that has already been seen in the current run resets the run counter
// to zero. Zero and not one, because the repeated frame does not count as new
// content -- it is a repeat by definition. The repeated frame then opens the
// next run. This is the longest all-distinct contiguous window.

const RATIO_DECIMALS = 6;
// Ratios are rounded to 6 decimals. Enough to keep 0.9999999999999999 noise
// out of a verdict, not enough to hide a real gap between two verdicts.

const MAX_BUFFER_BYTES = 256 * 1024 * 1024;
// stdout for -count_frames is one line; stdout for framemd5 is one ~80 byte
// row per frame. A long clip is millions of rows, and execFile kills the child
// with ENOBUFS if maxBuffer is exceeded, which would look exactly like a
// measurement failure. 256 MiB is far above any realistic session clip.

const TOOL_TIMEOUT_MS = 0;
// No timeout: -count_frames decodes the whole file and framemd5 decodes the
// whole file, so wall time scales with clip length and a fixed timeout would
// abort long recordings. The caller bounds this, not the process.

const INVALID_COUNT_MESSAGE =
  "ffprobe did not return a frame count; refusing to report 0 because 0 is a real value";
// Carried on the thrown error so the caller can distinguish "could not measure"
// from "measured zero" without string-matching a message.

const EMPTY_HASH_STREAM_MESSAGE =
  "framemd5 produced no hash rows; the file has no decodable video content";

// -- runner ----------------------------------------------------------------

// The only place a child process is started. Args are an ARRAY and go to
// execFile, which does not build a command line: a path containing a space, a
// quote or a semicolon cannot become a second command. Nothing here is ever
// concatenated into a shell string.
export async function runTool(bin, args, { maxBuffer = MAX_BUFFER_BYTES } = {}) {
  try {
    const { stdout, stderr } = await execFileAsync(bin, args, {
      encoding: "utf8",
      maxBuffer,
      timeout: TOOL_TIMEOUT_MS,
      windowsHide: true,
    });
    return { bin, args, code: 0, stdout, stderr };
  } catch (err) {
    // promisified execFile REJECTS on non-zero exit, which is what we want: a
    // missing file, a corrupt container or a missing encoder must never be
    // reported as a measurement. Re-attach the parts a caller needs so that
    // ffmpeg's own diagnostics -- the dropped-frame and corrupt-frame
    // warnings this whole module exists to reason about -- survive the throw
    // instead of being swallowed into a generic "command failed".
    err.exitCode = typeof err.code === "number" ? err.code : null;
    err.stderr = typeof err.stderr === "string" ? err.stderr : "";
    throw err;
  }
}

// -- guards ----------------------------------------------------------------

function assertPath(path) {
  if (typeof path !== "string" || path.trim().length === 0) {
    throw new TypeError(`path must be a non-empty string, got ${typeof path}`);
  }
  // Checked up front so "no such file" is an unmistakable error rather than an
  // ffprobe exit code that a caller has to decode. ffprobe is still the
  // authority on the file being a decodable video.
  let st;
  try {
    st = statSync(path);
  } catch (err) {
    throw new Error(`cannot measure a path that does not exist: ${path}`, { cause: err });
  }
  if (!st.isFile()) {
    throw new Error(`cannot measure a path that is not a regular file: ${path}`);
  }
  return st;
}

function assertPositive(value, name) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    throw new RangeError(`${name} must be a positive finite number, got ${String(value)}`);
  }
  return value;
}

function ratio(numerator, denominator) {
  // A zero denominator is a real state (a video stream with no frames) and
  // must not produce NaN, which would poison a verdict with a falsy-looking
  // value that is actually neither true nor false.
  if (!Number.isFinite(denominator) || denominator <= 0) return 0;
  const r = numerator / denominator;
  return Number.isFinite(r) ? Number(r.toFixed(RATIO_DECIMALS)) : 0;
}

// -- frame count -----------------------------------------------------------

// Strict parse of a -of csv=p=0 -count_frames payload.
function parseFrameCount(stdout) {
  const tokens = String(stdout)
    .split(/\r?\n/)
    .map((line) => line.trim())
    // Blank lines go FIRST. This single filter is the fix for the bug quoted
    // at the top of this file: the trailing newline becomes "" and
    // Number("") === 0, which is finite, which is indistinguishable from a
    // genuine zero-frame result.
    .filter((line) => line.length > 0);
  if (tokens.length === 0) {
    throw new Error(`${INVALID_COUNT_MESSAGE}: empty ffprobe output`);
  }
  if (tokens.length > 1) {
    throw new Error(`${INVALID_COUNT_MESSAGE}: expected one field, got ${tokens.length}`);
  }
  const token = tokens[0];
  // Only a bare run of digits is accepted. This rejects ffprobe's "N/A" (what
  // it prints when -count_frames cannot decode the stream) and any decimal or
  // signed form, instead of letting Number() manufacture a plausible integer.
  if (!/^\d+$/.test(token)) {
    throw new Error(`${INVALID_COUNT_MESSAGE}: non-numeric token ${JSON.stringify(token)}`);
  }
  return Number(token);
}

// How many frames the container actually holds, as ffprobe counted them.
export async function countFrames(path) {
  assertPath(path);
  const { stdout } = await runTool(FFPROBE_BIN, [...COUNT_FRAMES_ARGS, path]);
  return parseFrameCount(stdout);
}

// -- distinct content ------------------------------------------------------

// Every frame hash in decode order, comments dropped.
function parseFrameHashes(stdout) {
  return String(stdout)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .filter((line) => !line.startsWith(FRAMEMD5_COMMENT_PREFIX))
    // .at(), not [index]: FRAMEMD5_LAST_FIELD is a negative index counted from
    // the end and a plain bracket access with a negative number is always
    // undefined. ?? "" so a row with no comma field cannot throw mid-parse; it
    // is dropped by the filter below rather than counted as a frame.
    .map((line) => (line.split(",").at(FRAMEMD5_LAST_FIELD) ?? "").trim())
    .filter((hash) => hash.length > 0);
}

// total / distinct / longestUniqueRun from one framemd5 pass.
function summarizeHashes(hashes) {
  const total = hashes.length;
  let longestUniqueRun = 0;
  const seenInRun = new Set();
  for (const hash of hashes) {
    if (seenInRun.has(hash)) {
      // The picture repeated. The current streak is worthless.
      seenInRun.clear();
    }
    seenInRun.add(hash);
    if (seenInRun.size > longestUniqueRun) longestUniqueRun = seenInRun.size;
  }
  return {
    total,
    // Distinct across the WHOLE file, which is a different question from
    // longestUniqueRun: a clip can be mostly unique overall and still have a
    // long dead stretch. Both are reported.
    distinct: new Set(hashes).size,
    longestUniqueRun,
  };
}

// How many distinct pictures the clip contains. The count alone is reported for
// the caller who asked for a count; assessDelivery needs the contiguous run as
// well, so it calls summarizeFrames directly rather than paying for a second
// full decode.
export async function countDistinctContent(path) {
  const { total, distinct } = await summarizeFrames(path);
  if (total === 0) throw new Error(`${EMPTY_HASH_STREAM_MESSAGE}: ${path}`);
  return distinct;
}

async function summarizeFrames(path) {
  assertPath(path);
  const args = [
    ...LOGLEVEL_ARGS,
    FRAMEMD5_INPUT_FLAG, path,
    ...FRAMEMD5_OUTPUT_ARGS,
  ];
  const { stdout } = await runTool(FFMPEG_BIN, args);
  const hashes = parseFrameHashes(stdout);
  const { longestUniqueRun } = summarizeHashes(hashes);
  return { total: hashes.length, distinct: new Set(hashes).size, longestUniqueRun };
}

// -- the verdict -----------------------------------------------------------

// Does this clip carry enough NEW, CONSECUTIVE picture to stand in for the
// wall-clock span the caller expected?
export async function assessDelivery(path, expectedFps, expectedSeconds) {
  assertPath(path);
  assertPositive(expectedFps, "expectedFps");
  assertPositive(expectedSeconds, "expectedSeconds");

  // expectedFrames is the number of frame slots the clock budget implies at the
  // expected rate. This is the yardstick the contiguous run is measured
  // against, NOT deliveredFrames: a clip can deliver twice the frame count and
  // still be one frozen picture repeated twice as often.
  const expectedFrames = Math.round(expectedFps * expectedSeconds);

  // One decode each, in parallel: ffprobe counts, ffmpeg hashes. Neither reads
  // the other's output, so there is no ordering constraint between them.
  const [deliveredFrames, content] = await Promise.all([
    countFrames(path),
    summarizeFrames(path),
  ]);

  const longestUniqueRun = content.longestUniqueRun;

  // The percentage that is NOT sufficient. Kept in the verdict on purpose so a
  // caller can never accidentally read it as the answer.
  const coverage = ratio(content.distinct, deliveredFrames);

  // The percentage that IS the answer: how much of the expected timeline is a
  // single unbroken stretch of genuinely new picture.
  const contiguousRatio = ratio(longestUniqueRun, expectedFrames);

  // One full second of the clock, expressed in frames. Covering the clock means
  // covering at least this much consecutive distinct content -- one second of
  // real, changing picture is the floor for a transcript to have anything to
  // read, and it is the threshold the 85.1%-distinct / 20.8%-contiguous clip
  // fails.
  const oneSecondOfClock = expectedFps;

  return {
    path,
    expectedFps,
    expectedSeconds,
    expectedFrames,
    deliveredFrames,
    distinctFrames: content.distinct,
    longestUniqueRun,
    coverage,
    contiguousRatio,
    contentSufficientToCoverClock: longestUniqueRun >= oneSecondOfClock,
  };
}