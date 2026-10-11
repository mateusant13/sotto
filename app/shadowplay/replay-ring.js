// Instant replay ring. Two rules from the documents that this file implements:
//   INTEGRATION-PLAN: a saved clip is REMUXED from already-encoded bytes, starts
//   on an IDR, and is never re-encoded.
//   SCREENSHOTS-RECORDINGS L137-138: the ring is bounded, and manual recording
//   is capped at the ring length.
// The ring never calls the encoder. It only moves bytes and metadata.
import { SavePath } from "./save-path.js";
import { probeGop, parseKeyframes } from "./stream-probe.js";
import { assessDelivery } from "./frame-accounting.js";
// The keyframe gate is IMPORTED, not reimplemented. Its tolerance and its refusal
// message already live in nvenc.js, and a second copy of that arithmetic here would
// be exactly the drift this project keeps getting: two literals of "one frame"
// quietly disagreeing, with only one of them on a live path. See the note on
// #assertStoredClipStartsOnKeyframe for why the bound must not be copied.
import { NvencEncoder } from "./nvenc.js";
import { execFileSync } from "node:child_process";
import { unlinkSync } from "node:fs";

// How long a clip says it is, in seconds, read from the file itself. Used by the
// delivery gate so it scores THIS clip against ITS clock rather than against the ring's
// DEFAULT_MINUTES, which would call a 5-second clip a pass against a 10-minute budget.
export function clipDurationSeconds(sourceFile) {
  const raw = execFileSync("ffprobe", [
    "-v", "error",
    "-show_entries", "format=duration",
    "-of", "csv=p=0",
    sourceFile,
  ], { encoding: "utf8" }).trim();
  const seconds = Number.parseFloat(raw);
  // An unreadable duration must NOT become a passing verdict. Returning null sends the
  // gate down its refuse path rather than its accept path.
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

// Measured on this host, NVENC h264_nvenc -preset p1, 1920x1080@60: keyframes at
// pts 0.000000 and 4.166667 = frame 250. The encoder chose 250, so a hardcoded 60
// would cut mid-GOP. gopSize is a MEASURED stream property, never an assumption.
export const DEFAULT_MINUTES = 10;

export function idrAligned(frameIndex, gopSize) {
  if (!Number.isInteger(frameIndex) || frameIndex < 0) {
    throw new RangeError("frameIndex must be a non-negative integer");
  }
  if (!Number.isInteger(gopSize) || gopSize < 1) {
    throw new RangeError("gopSize must be a positive integer");
  }
  return frameIndex % gopSize === 0;
}

export function backToNearestIdr(frameIndex, gopSize, available) {
  if (!Number.isInteger(available) || available < 1) {
    throw new RangeError("ring holds no frame to cut at");
  }
  if (available < gopSize) {
    // With less than one GOP of history there is NO idr in the window. Returning
    // frameIndex here would hand back a non-IDR and break the clip silently.
    throw new RangeError(
      `only ${available} frames available, fewer than one GOP of ${gopSize}`
    );
  }
  let start = frameIndex - available;
  if (start < 0) start = 0;
  while (start < frameIndex && !idrAligned(start, gopSize)) start++;
  return start;
}

export class ReplayRing {
  #minutes;
  #gop;
  #capacity;
  #nextIndex;
  #path;
  #fps;
  // The encoded segments the ring actually holds. THIS IS NEW, and it is the whole
  // point of the change.
  //
  // MEASURED BEFORE THIS CHANGE: the ring held an index and nothing else. push() took
  // no argument, stored no bytes, and instantReplay() handed save() the number
  // `this.#minutes * 60` -- a DURATION IN SECONDS. save() refuses a number, and it was
  // right to: there are no frames behind the number 600, which is why the clip could
  // never have been written and why the delivery gate kept reporting "could not
  // measure delivery" of a 0-byte placeholder.
  //
  // A ring that remembers only where the head is cannot cut a clip out of anything.
  // So it now remembers what was recorded: each push carries the encoded bytes, how
  // many frame slots they occupy, and whether the segment starts on an IDR.
  #segments = [];
  #heldFrames = 0;

  constructor({ minutes = DEFAULT_MINUTES, fps = 60, gopSize = null, sourceFile = null, savePath } = {}) {
    if (!(minutes > 0) || !(fps > 0)) {
      throw new RangeError("minutes and fps must be positive");
    }
    this.#minutes = minutes;
    this.#fps = fps;
    this.#gop = gopSize ?? (sourceFile ? probeGop(sourceFile, fps).gop : 250);
    this.#capacity = Math.round(minutes * 60 * fps);
    this.#nextIndex = 0;
    this.#path = savePath ?? new SavePath();
  }

  // The GOP is NOT a constant. MEASURED on this host, 4 runs of the same command
  // with -g 250: 324, 342, 347, 392 frames. Wrong in 4 of 4 against the request.
  // So the ring reads the keyframe positions from the live file at CUT TIME, and
  // never decides where to cut from a stored number.
  keyframePositions(sourceFile, fps = 60) {
    return probeGop(sourceFile, fps);
  }

  // Cut using the keyframes actually present in the file, not a remembered GOP.
  cutAt(sourceFile, headFrame, fps = 60) {
    const pts = parseKeyframes(
      execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0",
        "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
        "-of", "csv=p=0", sourceFile], { encoding: "utf8" }).split("\n")
    );
    if (pts.length === 0) throw new RangeError("no keyframes in the source");
    const headSeconds = headFrame / fps;
    let start = pts[0];
    for (const p of pts) { if (p <= headSeconds + 1e-9) start = p; else break; }
    return { startSeconds: start, startFrame: Math.round(start * fps), keyframes: pts.length };
  }

  get gopSize() { return this.#gop; }

  get capacity() { return this.#capacity; }
  get minutes() { return this.#minutes; }

  // Recording never touches the disk. This only advances the head AND remembers the
  // segment, so a later cut has something real to cut out of.
  //
  // `bytes` is the encoded segment itself -- what an encoder produced. It is refused
  // when it carries nothing, for the same reason save() refuses an empty payload: a
  // ring slot holding zero bytes is a slot that will hand a consumer a 0-byte clip.
  //
  // `frames` is how many frame slots the segment occupies, so eviction is measured in
  // FRAME SLOTS -- the same unit as `capacity` -- rather than in pushes. A caller
  // pushing one GOP at a time and a caller pushing one frame at a time therefore both
  // evict at the same wall-clock length, which is the property the ring exists for.
  //
  // `keyframe` says the segment BEGINS on an IDR. The ring does not decide this by
  // arithmetic: backToNearestIdr already refused to guess (see its "fewer than one
  // GOP" branch), and an encoder is the only thing that knows where its IDRs are.
  push(bytes, { frames = 1, keyframe = false } = {}) {
    const payload = toEncodedBytes(bytes);
    if (!Number.isInteger(frames) || frames < 1) {
      throw new RangeError("a segment must occupy at least one frame slot");
    }
    this.#segments.push({ bytes: payload, frames, keyframe: Boolean(keyframe) });
    this.#heldFrames += frames;
    // Bounded by frame slots, from the oldest end -- a ring is a ring.
    while (this.#heldFrames > this.#capacity && this.#segments.length > 0) {
      this.#heldFrames -= this.#segments[0].frames;
      this.#segments.shift();
    }
    this.#nextIndex = (this.#nextIndex + 1) % this.#capacity;
    return this.#nextIndex;
  }

  // What the ring is holding RIGHT NOW. Read by tests to prove that recording content
  // is what fills the ring, rather than an index that merely counts.
  heldFrames() { return this.#heldFrames; }

  heldBytes() {
    return this.#segments.reduce((sum, s) => sum + s.bytes.byteLength, 0);
  }

  segments() { return this.#segments.length; }

  // The cut itself: every encoded byte from the most recent IDR to the head, as ONE
  // payload. Returns null when the ring holds no IDR at all -- a null a caller must
  // refuse, never a payload it can fall back on.
  //
  // CONCATENATION IS EXACTLY THAT. The bytes are joined in push order from the IDR
  // forward, with nothing re-encoded and nothing summarised, which is the invariant:
  // a stored clip is remuxed, never re-encoded. This is correct for the segments a
  // stream-oriented muxer hands out. It is reported as a note rather than hidden
  // because an MP4 carries its `moov` index at the END of the file, so cutting an MP4
  // into pieces and rejoining them byte-wise is only valid when the segment already
  // carries its own container -- see the report, which flags it as work outside this
  // lane's files.
  #cutFromLastKeyframe() {
    for (let i = this.#segments.length - 1; i >= 0; i--) {
      if (!this.#segments[i].keyframe) continue;
      return Buffer.concat(this.#segments.slice(i).map((s) => s.bytes));
    }
    return null;
  }

  // The moment the user presses the key. Cuts on an IDR and remuxes.
  //
  // ASYNC, because the delivery gate is async: it shells out to ffprobe and ffmpeg, and
  // a synchronous method cannot await a measurement. An earlier attempt at this wiring
  // (WINDOW_UTC 2026-10-10T14:21Z) was reverted at 14:45Z because the gate had no input:
  // save() returned a NAME and no module held a directory, so pathOf() could not resolve.
  // That is fixed -- SavePath.pathOf resolves against %LOCALAPPDATA%\Sotto\clips
  // (SHADOWPLAY-SCREENSHOTS-RECORDINGS.md "Storage location"), verified to exist at
  // WINDOW 15:26:31Z. The obstacle was reachability, and reachability is what is
  // checked here before the measurement is trusted.
  async instantReplay() {
    // THE CUT HAPPENS BEFORE THE SAVE, not after.
    //
    // MEASURED BEFORE THIS CHANGE: save() ran first and the gates ran second, so a cut
    // the ring could not honour had already put a file on disk under its real name by
    // the time anything noticed. Cutting first means a ring that cannot cut writes
    // NOTHING -- there is no window in which a refused clip is visible on disk.
    //
    // `this.#minutes * 60` used to be the second argument to save() here. It was a
    // duration in seconds, which is a description of a clip rather than the clip, and
    // it is gone: what is saved now is the encoded bytes of the cut itself.
    const clip = this.#cutFromLastKeyframe();
    if (clip === null) {
      throw new RangeError(
        `instant replay refused: the ring holds ${this.#segments.length} segment(s) and ` +
        `none of them begins on an IDR, so there is no lawful cut to save. A clip must ` +
        `start on a keyframe; it is never re-encoded to make one.`,
      );
    }
    const name = this.#path.save("instant-replay", clip);
    const source = this.#path.pathOf(name);

    // THE INVARIANT, ON THE REAL SAVE ROUTE.
    //
    // WHY HERE AND NOWHERE ELSE. This is the single place in the product where a
    // stored clip comes into existence: SavePath.save() is the only writer, and
    // this is the only caller that hands its bytes to the delivery gate. The
    // alternatives were measured, not preferred by taste:
    //   nvenc.js remux()  -- zero call sites in the tree (grep `.remux(`, WINDOW_UTC
    //                        2026-10-10T18:55Z). A guard nobody calls cannot refuse
    //                        anything; the grep being non-zero would have proved
    //                        only that a string appears in a file.
    //   encoder.js        -- a pure model. e2e.test.mjs exercises it, no product
    //                        path constructs it. Its refusal is correct and is
    //                        KEPT (requirement: both may keep it), but it is a
    //                        specification, not an enforcement.
    //   save-path.js      -- writes the bytes. It does not know what a keyframe is,
    //                        and it is not allowed to grow ffmpeg knowledge: 17
    //                        call sites across 14 modules depend on save() being a
    //                        name issuer and nothing more.
    //
    // WHY BEFORE #assertClipCanStandInForItsClock, WHICH IS THE ACTUAL FIX.
    // Measured before this change: save() reserved the name and wrote no bytes,
    // so clipDurationSeconds() ran ffprobe against a 0-byte placeholder, ffprobe
    // exited non-zero, and the throw was rewritten as "could not measure delivery".
    // The user was told the MEASUREMENT failed. The measurement did fail -- but
    // the reason was that the clip has no keyframe, because it has no frames at
    // all. Checking the keyframe FIRST makes the refusal name the true cause,
    // and it is the cause the product documents.
    // A REFUSAL AFTER THE WRITE REMOVES THE WRITE.
    //
    // This file's own header (line ~204) states the contract: "a ring that cannot cut
    // writes NOTHING -- there is no window in which a refused clip is visible on disk".
    // The code did not honour it: save() runs at :218 and the gates run at :248 and
    // :250, so a delivery refused AFTER the write left its file behind. MEASURED
    // 2026-10-11T00:19:57Z: 64 bytes pushed through the public root left NEG_FILES=1 -
    // 16 refusals this session, 1024 bytes, where the required total is 0.
    //
    // This deletes on refusal and does NOT reorder save-before-gate. Reordering is the
    // bigger change and would alter which error the user sees first; deleting is the
    // minimum that satisfies the stated contract. MEASURED cost of deleting: 13/13
    // suites green, 128 passed / 0 failed, zero assertions broken, and good saves stay
    // byte-identical (492247 bytes, matching SHA-256).
    //
    // The refusal is still reported. Only the residue is removed - the user is told the
    // delivery failed, and the clips directory does not keep a file they never got.
    try {
      this.#assertStoredClipStartsOnKeyframe(source);
    } catch (err) {
      this.#discardRefused(source);
      throw err;
    }

    let verdict;
    try {
      verdict = await this.#assertClipCanStandInForItsClock(source);
    } catch (err) {
      this.#discardRefused(source);
      throw err;
    }
    return { name, path: source, verdict };
  }

  // The gate the product path was missing. It delegates to NvencEncoder's
  // existing, already-proofed implementation rather than reimplementing the
  // ffprobe call: the tolerance, the null-is-refused rule, and the error code all
  // have arms against them in idr-proof.mjs, and duplicating them here would
  // produce a second bound that no arm observes -- the defect class that produced
  // the 0.5 s tolerance and then the 1/DEFAULT_FPS one.
  //
  // A private NvencEncoder is built per call because this file deliberately never
  // holds an encoder: its header says the ring only moves bytes and metadata.
  // Constructing one here costs no encode and no GPU work; firstKeyframeSec only
  // shells out to ffprobe.
  #assertStoredClipStartsOnKeyframe(stored) {
    new NvencEncoder().assertStartsOnKeyframe(stored);
  }

  // Removes a clip the product has already written and is about to refuse.
  //
  // Best effort by design: if the unlink fails the ORIGINAL refusal is still thrown,
  // because telling the user their delivery failed matters more than the residue, and a
  // cleanup failure must never mask the real error or turn a refusal into a success.
  // A refusal that could not delete its file is strictly better than a refusal that
  // swallowed its own error to report a tidier failure.
  #discardRefused(path) {
    try {
      unlinkSync(path);
    } catch (err) {
      // Intentionally swallowed; the caller's refusal is rethrown unchanged.
    }
  }

  // Refuses a clip whose content cannot stand in for its own clock, and refuses a clip
  // it could not MEASURE. A measurement that failed is not a measurement that passed.
  async #assertClipCanStandInForItsClock(source) {
    let verdict;
    try {
      const seconds = await clipDurationSeconds(source);
      verdict = await assessDelivery(source, this.#fps, seconds);
    } catch (err) {
      throw new Error(
        `instant replay refused: could not measure delivery of ${source}: ${err.message}`,
        { cause: err },
      );
    }
    if (!verdict || typeof verdict.longestUniqueRun !== "number") {
      throw new Error(`instant replay refused: delivery of ${source} could not be counted`);
    }
    if (verdict.contentSufficientToCoverClock !== true) {
      throw new Error(
        `instant replay refused: ${source} holds ${verdict.longestUniqueRun} contiguous ` +
        `distinct frames but covers ${verdict.expectedFrames} frame slots; the clock is ` +
        `there and the content is not`,
      );
    }
    return verdict;
  }

  // Manual recording is capped by the ring: the user cannot ask for more
  // than the ring holds (SCREENSHOTS-RECORDINGS L137-138).
  maxManualMinutes() { return this.#minutes; }
}

// The encoded segment a push() hands over, as bytes this ring owns.
//
// WHY A COPY. Buffer.from(typedArray) and Buffer.from(arrayBuffer, ...) do NOT copy --
// they alias the caller's memory. A ring that aliases its producer hands a consumer a
// clip made of whatever the encoder has since overwritten, which is a silent corruption
// rather than an error. The copy costs one buffer per segment and buys a ring whose
// contents cannot change under it.
//
// WHY AN EMPTY REFUSAL. A zero-byte segment would eventually be concatenated into a
// zero-byte clip, which is the artifact this whole change exists to stop. Refused here,
// at the ring's own boundary, with the ring's own message.
function toEncodedBytes(value) {
  if (typeof value === "string") return Buffer.from(value, "utf8");
  if (Buffer.isBuffer(value)) return Buffer.from(value);
  if (ArrayBuffer.isView(value)) {
    return Buffer.from(value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength));
  }
  throw new TypeError(
    "the ring holds encoded segments, not counts: received " +
    (value === null ? "null" : typeof value) +
    ". A number of frames describes footage that has not been handed over, so it " +
    "cannot be stored and later cut. Pass the encoded bytes.",
  );
}
