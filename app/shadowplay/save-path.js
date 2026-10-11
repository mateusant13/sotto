// The one save path. Every capture route (hotkey, instant replay, highlights,
// manual recording) goes through save(); none of them writes a file itself.
// Phase 6 "Done when" (INTEGRATION-PLAN L129): all save paths go through the
// one writer.
import { ClipWriter } from "./clip-writer.js";
import { mkdirSync, statSync, unlinkSync } from "node:fs";
import { join } from "node:path";

export const ROUTES = ["hotkey", "instant-replay", "highlights", "manual"];

// Where saved clips live, per SHADOWPLAY-SCREENSHOTS-RECORDINGS.md "Storage location"
// (section added 2026-10-10; before it, no document specified a location -- measured
// at WINDOW_UTC 2026-10-10T15:22:45Z, population = 8 directory names searched under
// H:\sotto, 14 app files, 9 design docs, zero references).
//
// %LOCALAPPDATA%\Sotto\clips, resolved through the environment rather than hardcoded.
// The platform defines where per-user app data belongs, so this is a platform fact and
// not an invented directory. Clips are user data, so they belong under the user's own
// tree and not inside the install directory -- writing into app\shadowplay would make
// a packaged or read-only install unable to record, and would dirty a git tree.
export const APP_FOLDER = "Sotto";
export const CLIPS_FOLDER = "clips";

// Returns the clips directory, or null when the environment does not define one.
// Null is honest: it means "this host has no per-user app data root", and a caller
// that gets null cannot accidentally pretend it has a path.
export function defaultClipsDir(env = process.env) {
  const root = env.LOCALAPPDATA ?? env.APPDATA;
  if (typeof root !== "string" || root.length === 0) return null;
  return join(root, APP_FOLDER, CLIPS_FOLDER);
}

// Creates the directory if it is missing and returns it. Exported so the composition
// root can prepare the location once at startup rather than racing on first capture.
export function ensureClipsDir(env = process.env) {
  const dir = defaultClipsDir(env);
  if (dir === null) {
    throw new Error(
      "no per-user application data directory: neither LOCALAPPDATA nor APPDATA is set",
    );
  }
  mkdirSync(dir, { recursive: true });
  return dir;
}

// The writer a SavePath gets when the caller injects none.
//
// It used to be `new ClipWriter({ exists: () => false })` -- a predicate that
// answers "nothing is taken" for every name, forever. A path helper that believes
// the disk is empty hands out 0000.mp4 to every session that ever starts, and the
// second session's clip overwrites the first one's. MEASURED 2026-10-10 on this host,
// before this function existed: with 0000.mp4 already on disk, two default SavePaths
// both returned 0000.mp4.
//
// So the default writer points at the REAL clips directory instead of assuming it is
// empty. Only the e2e test and the perf probe ever injected a listing-backed writer,
// so every production construction was exposed.
//
// Returns the writer together with the preparer it needs. ClipWriter reserves a name
// with O_CREAT|O_EXCL whenever a `dir` is set, which bypasses the `exists` predicate
// entirely -- measured 2026-10-10T13:10Z, the writer reached openSync before anything
// had made the directory and failed ENOENT. So the directory must be created by
// save() BEFORE the writer claims a name, which is why this returns the pair rather
// than the writer alone.
export function defaultClipWriter(env = process.env) {
  const dir = defaultClipsDir(env);
  let prepared = false;

  const prepare = () => {
    if (prepared) return dir;
    if (dir === null) {
      throw new Error(
        "cannot choose a clip name: neither LOCALAPPDATA nor APPDATA is set, " +
        "so the clips directory is unknown and no name can be shown to be free",
      );
    }
    try {
      mkdirSync(dir, { recursive: true });
    } catch (cause) {
      throw new Error(
        `cannot prepare the clips directory ${dir}: ${cause.code ?? cause.message}`,
        { cause },
      );
    }
    prepared = true;
    return dir;
  };

  // One predicate, handed to the writer AND returned to the caller.
  //
  // It used to be created inline as `exists: (name) => existsOnDisk(prepare, name)` and
  // left inside the closure, which made it unobservable -- and unobservable made it untested.
  // ClipWriter#claim consults `exists` ONLY when `dir` is null (clip-writer.js:92), and `dir`
  // here is non-null on every host that has a data root, so O_EXCL answered first.
  //
  // MEASURED 2026-10-10T19:16Z on this host, with a call counter inside existsOnDisk across
  // three constructions: the DEFAULT writer was called 0 times (O_EXCL supersedes it), while
  // a dir-less writer injected into SavePath -- a supported public construction -- was called
  // and propagated prepare()'s refusal. So the entry is LIVE on the degraded path and DEAD on
  // the default one; "0 calls" alone would have been a measurement of one construction only.
  // Returning it makes both observable over a real directory instead of asserted in a comment.
  //
  // What stays unreachable is the statSync line itself, and provably: it can only run when
  // prepare() returned a non-null dir, and prepare() returns the very `dir` this writer was
  // built with, so a non-null answer implies writer.dir !== null -- which is exactly the case
  // where #claim never calls this predicate. No configuration reaches it. Making it live means
  // editing clip-writer.js:92, which is outside this file's ownership; until then the belt is
  // verified rather than worn, which is stated here rather than implied by silence.
  const exists = (name) => existsOnDisk(prepare, name);
  // dir stays null when the environment defines none, so pathFor() keeps returning the
  // bare name for such hosts instead of joining against "null".
  const writer = new ClipWriter({ dir, exists });
  return { writer, prepare, exists };
}

// The predicate the default writer hands over. It reads the directory at call time
// rather than caching a listing at construction: a clip written after the SavePath was
// built is still a clip that must be skipped. With a `dir` set this is the belt to
// the writer's O_EXCL braces -- it decides what a caller is told when it has no
// directory, and it keeps the "consult the real directory" property true of this file.
function existsOnDisk(prepare, name) {
  // prepare() either returns a real directory or throws; it never returns null.
  //
  // This branch used to be `if (dir === null) return false`, and returning false from an
  // exists() predicate means "this name is FREE". That is the permissive answer -- the one
  // that hands out a name an existing directory already holds, and sends the write down the
  // create path. It was unreachable for as long as prepare() threw on a null dir, which is
  // precisely what made it a landmine: the safety was incidental rather than structural, and
  // any later edit that let prepare() return null would have reinstated the permissive
  // predicate with no test failing. So the invariant is now stated as a throw, which is a
  // property of this function rather than of prepare()'s current implementation.
  const dir = prepare();
  if (dir === null) {
    throw new Error(
      "cannot inspect a clips directory that does not exist: answering exists() with " +
      "'false' would claim a name that is already taken",
    );
  }
  try {
    return statSync(join(dir, name), { throwIfNoEntry: false }) !== undefined;
  } catch (cause) {
    throw new Error(
      `cannot inspect the clips directory ${dir}: ${cause.code ?? cause.message}`,
      { cause },
    );
  }
}

// How many bytes `data` carries, or null when it carries none.
//
// THE DECISION, stated once so it is not re-litigated at a call site: save() refuses a
// caller that supplies no bytes. It does not write an empty file on the caller's behalf.
//
// The alternative was considered and rejected on evidence rather than taste. Every one of
// the three production call sites passes a NUMBER today -- replay-ring.js:130 passes
// `this.#minutes * 60` (a duration in seconds, not even a byte count), audio-track.js:61
// passes `frames`, captions.js:53 passes `text.length`. A length is a description of
// content that nobody has. There is no mp4 behind the number 300, so the only file the
// old contract could honestly produce was the 0-byte placeholder -- which is the defect,
// measured at POP=10 real files and every one of them empty.
//
// So the refusal is not a tightening for its own sake: it is the only answer that cannot
// ship a clip a consumer will enumerate and fail to play. A capture that breaks is a
// capture the owner is told about; a capture that writes nothing is the bug that shipped.
//
// The zero-length case is deliberately NOT duplicated here. An empty Buffer or string is a
// well-formed payload of zero bytes, and ClipWriter#writeClip already refuses it (before it
// claims any name, so nothing is left behind). One rule, one owner: this function decides
// whether there is a payload at all, the writer decides whether it is big enough.
function whatCountsAsPayload(data) {
  if (typeof data === "string") return Buffer.byteLength(data, "utf8");
  if (ArrayBuffer.isView(data)) return data.byteLength;
  if (data === null || data === undefined) {
    throw new TypeError(
      "save() was given no clip: a saved clip must carry the encoded bytes, not the " +
      "absence of them. An empty file is the defect this path was changed to end, so " +
      "nothing is reserved and nothing is written.",
    );
  }
  throw new TypeError(
    "save() needs the clip's bytes, not its length: received " +
    (typeof data === "number" ? `the number ${data}` : `a ${typeof data}`) +
    ". A length is not content -- there are no bytes to write -- so the call is refused " +
    "rather than turned into an empty file. Pass the encoded clip as a string, Buffer or " +
    "TypedArray.",
  );
}

export class SavePath {
  #writer;
  #written;
  #blocked;
  #leaked;
  #prepare;

  constructor({ writer, env = process.env } = {}) {
    // An injected writer always wins: the e2e test and the perf probe point theirs at
    // their own directory, and a caller that knows where its clips go is not overruled.
    // Only the default writer needs its directory prepared.
    if (writer) {
      this.#writer = writer;
      this.#prepare = null;
    } else {
      const fallback = defaultClipWriter(env);
      this.#writer = fallback.writer;
      this.#prepare = fallback.prepare;
    }
    this.#written = [];
    this.#blocked = [];
    this.#leaked = [];
  }

  // The single write. Returns the name it used, or throws. No route bypasses this.
  //
  // `data` is the ENCODED CLIP, not a length. This is the change that ends the 0-byte
  // defect the product shipped. Measured before it: POP=10 real files in
  // %LOCALAPPDATA%\Sotto\clips, every one of them 0 bytes, because save() called
  // nextClipName(), which reserves a name with O_CREAT|O_EXCL and closes the descriptor
  // without ever putting bytes in. The reservation was the whole of it, so
  // ReplayRing.instantReplay could not succeed by construction: ffprobe was handed a file
  // with no frames, and the failure was reported as "could not measure delivery".
  //
  // It now hands the payload to ClipWriter#writeClip, which claims the name and writes
  // through the SAME descriptor that proved the claim, so the name and the content are
  // one inode and there is no window in which a reserved name sits empty.
  //
  // A caller that supplies no bytes is REFUSED, not served. See whatCountsAsPayload for
  // the whole decision; the short form is that a length is not content, and the only
  // file a length can produce is the empty one this line of code existed to stop.
  save(route, data) {
    if (!ROUTES.includes(route)) {
      throw new RangeError(`unknown save route: ${route}`);
    }
    const length = whatCountsAsPayload(data);
    // The real directory is created here, on the first capture, and not in the
    // constructor: ReplayRing, Captions and AudioTrack all build a SavePath, and merely
    // building one should not touch the filesystem. A directory that cannot be created
    // makes save() throw a named error rather than fall back to "the disk is empty",
    // because that fallback is the bug this file was changed to remove.
    this.#prepare?.();
    const name = this.#writer.writeClip(data);
    // BOOKKEEPING FAILS AFTER THE BYTES LANDED -> UNDO THE WRITE.
    //
    // writeClip() returns with the clip on disk. Everything after that is bookkeeping,
    // and bookkeeping can fail - an allocation, a frozen array, a patched field. If it
    // does, the caller receives a refusal while a complete, playable clip sits in the
    // clips directory under a name nobody was told about. That contradicts the
    // contract replay-ring.js states: a refused clip is never visible on disk.
    //
    // The fix lives HERE, not at the call site, because this is where the window is:
    // every caller of save() inherits the repair, and the caller cannot see or undo a
    // partial save it never received the name of.
    //
    // Measured: 344ab2c wrapped the two GATE calls in the ring module and left this
    // window open, and the reviewer found the gap before it was killed by a shutdown.
    try {
      this.#written.push({ route, name, bytes: length });
    } catch (err) {
      // Best effort, and silent on purpose: the bookkeeping failure is the error the
      // caller must see. A cleanup failure here must not replace it with a different
      // one, and must not convert a refusal into a success.
      try {
        unlinkSync(this.#writer.pathFor(name));
      } catch {
        // The clip stays. Reported rather than hidden: this is the one case where the
        // contract cannot be honoured, so it is counted instead.
        this.#leaked.push({ route, name });
      }
      throw err;
    }
    return name;
  }

  // Clips that save() could not remove after a bookkeeping failure. Counted so the
  // residue is visible rather than inferred from disk state.
  leaked() {
    return this.#leaked.map((l) => l.name);
  }

  // The path of a name this SavePath issued, for callers that must MEASURE the clip
  // (ffprobe needs a path, not a name). Returns the bare name when the writer has no
  // directory configured, so existing callers are unaffected. save() still returns the
  // NAME -- its return type is unchanged on purpose, because 17 call sites depend on it.
  pathOf(name) {
    return this.#writer.pathFor(name);
  }

  // A failed save must be visible. Silently writing nothing is indistinguishable
  // from a crash (CAPTURE-PIPELINE L95-97), so failures are recorded, not swallowed.
  recordFailure(route, error) {
    this.#blocked.push({ route, error: String(error) });
    return this.#blocked.length;
  }

  written() { return this.#written.map((w) => w.name); }
  blocked() { return this.#blocked.length; }
}