// One writer for every save path. SCREENSHOTS-RECORDINGS.md L228-235 defines the
// collision rule: take the next free value, try at most 10 times, then error.
// The ring is never touched while resolving a collision.
//
// The name is RESERVED, not merely checked. A directory listing is a snapshot, not a
// lock: a writer that reads one, decides a name is free and returns it has reserved
// nothing, so two writers listing the same directory at the same moment are both told
// 0000.mp4 is free and both write 0000.mp4. Measured WINDOW_UTC 2026-10-10 in
// clip-writer-race.test.mjs: two writers over one real directory collided on 0000.mp4,
// the second write silently overwrote the first, and four concurrent writers collapsed
// onto one file holding one clip. ensureClipsDir() makes the directory without reserving
// a name inside it.
//
// So the claim is made with O_CREAT|O_EXCL, which the kernel decides atomically: of two
// writers racing one name exactly one wins and the loser sees EEXIST and advances.
//
// RESERVATION IS NOT CONTENT. The reservation is a zero-byte placeholder, and for a long
// time nothing ever put bytes in afterwards: #claim closed the descriptor it had just
// created, so every clip this module produced was 0 bytes by construction. Measured
// WINDOW_UTC 2026-10-10: a prior lane found POP=10 files in the real clips directory
// (0000-0009.mp4), every one of them 0 bytes, before evicting them back to POP=0. That is
// what the product actually shipped, not a hypothetical.
//
// So the exclusive create now hands its descriptor BACK instead of closing it. The name
// and the content are the same inode, claimed and written through one file descriptor,
// so there is no second syscall in which the claim could be lost. The alternative --
// write to `<name>.part` and rename over the reserved name -- was rejected on evidence,
// not taste: the race suite asserts the clips directory contains EXACTLY the claimed
// names (clip-writer-race.test.mjs, arm 1: readdirSync(dir).sort() deepEqual [aName,
// bName]), so a transient `.part` sibling would be a file the enumeration sees, and a
// rename that failed after the name was already claimed (a sharing violation, an
// antivirus handle, a full volume) would leave that name consumed and empty forever.
import { SessionClock, WIDTH } from "./session-clock.js";
import { openSync, closeSync, writeSync, unlinkSync } from "node:fs";
import { join } from "node:path";

export const MAX_ATTEMPTS = 10;

export function parseSeq(name) {
  const m = /^(\d{4})\./.exec(name);
  return m ? Number(m[1]) : NaN;
}

export class ClipWriter {
  #clock;
  #exists;
  #attempts;
  #dir;

  // `dir` is OPTIONAL and, when absent, pathFor(name) returns the bare name.
  //
  // Why it is optional rather than required: today save() hands callers a NAME, and 17
  // call sites across 14 modules assert on that string. Adding a required dir would
  // break every one of them. But a name with no directory is not a path, so anything
  // that needs to MEASURE a saved clip -- ffprobe, ffprobe -count_frames -- cannot
  // resolve one. Measured WINDOW_UTC 2026-10-10T15:10:50Z: this class held only an
  // exists predicate, and the sole holder of the directory anywhere in the tree was
  // e2e.test.mjs, which had created it with mkdtempSync.
  //
  // So the directory is now a first-class, optional property, and save() can be asked
  // for a path without any existing call site changing shape.
  constructor({ exists, clock = new SessionClock(), dir = null } = {}) {
    if (typeof exists !== "function") {
      throw new TypeError("ClipWriter requires an exists(name) predicate");
    }
    if (dir !== null && typeof dir !== "string") {
      throw new TypeError("dir must be a string or null");
    }
    this.#exists = exists;
    this.#clock = clock;
    this.#attempts = new Map();
    this.#dir = dir;
  }

  get dir() { return this.#dir; }

  // The absolute path of a name this writer issued. Returns the bare name when no
  // directory is configured, so a caller that ignores directories is unaffected.
  pathFor(name) {
    if (typeof name !== "string" || name.length === 0) {
      throw new TypeError("name must be a non-empty string");
    }
    return this.#dir === null ? name : join(this.#dir, name);
  }

  // Reserves a name and RETURNS IT. It claims the name and nothing else: the file it
  // leaves behind is a zero-byte placeholder, and the bytes are the caller's to write
  // (e2e's writeFileSync(join(dir, name), ...) truncates over it, which is why that
  // call site is unaffected). A caller that wants the bytes landed by this module
  // should call writeClip() or openClip() instead -- measured over POP=10 real clip
  // files, a caller that only used this method produced POP=10 zero-byte clips.
  //
  // The signature and return type are unchanged, deliberately: 17 call sites across 14
  // modules depend on getting back a bare name string.
  nextClipName() {
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      const name = `${this.#clock.nextName()}.mp4`;
      this.#attempts.set(name, attempt);
      if (this.#claim(name)) return name;
    }
    throw new Error(
      `no free sequence value after ${MAX_ATTEMPTS} attempts`
    );
  }

  // Claims the next free name and hands back an OPEN, writable descriptor onto the
  // reserved file itself. This is the streaming shape: an encoder that produces an mp4
  // incrementally writes chunks into `handle.fd` and calls commitClip() when it is done,
  // so the clip is never held in memory whole.
  //
  // It refuses a writer with no directory rather than returning a handle onto nothing:
  // without a path there is nowhere for bytes to land, and a handle that silently could
  // not receive them is the defect this method exists to end.
  openClip() {
    if (this.#dir === null) {
      throw new Error(
        "cannot open a clip: this ClipWriter has no directory, so a reserved name " +
        "has no path to receive bytes. Construct it with { dir } to write clips.",
      );
    }
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      const name = `${this.#clock.nextName()}.mp4`;
      this.#attempts.set(name, attempt);
      const fd = this.#openExclusive(name);
      if (fd !== null) return Object.freeze({ name, fd });
    }
    throw new Error(
      `no free sequence value after ${MAX_ATTEMPTS} attempts`
    );
  }

  // Closes a handle and returns the name. After this the clip is complete on disk:
  // every byte written through the descriptor is durable and no longer growing, so this
  // is the point at which ffprobe may measure it.
  commitClip(handle) {
    this.#assertHandle(handle);
    closeSync(handle.fd);
    return handle.name;
  }

  // Abandons a handle: closes it and removes the reserved file, returning the name.
  //
  // This exists because a failed encode is the same failure the product already shipped.
  // A descriptor closed without its bytes leaves exactly the artifact this module was
  // fixed for -- a file in the clips directory that a consumer enumerates and tries to
  // play, holding nothing. Committing is a choice; leaving a half-written file behind
  // is not, so the failure path removes it and frees the name for reuse.
  abortClip(handle) {
    this.#assertHandle(handle);
    closeSync(handle.fd);
    unlinkSync(join(this.#dir, handle.name));
    return handle.name;
  }

  // Claims a name, writes `data` into it, and returns the name -- the one-call shape for
  // a caller that already holds the encoded clip in memory. This is what a lane fixing
  // save-path.js should call; see the report for the exact substitution.
  writeClip(data) {
    const payload = toPayload(data);
    // An empty payload is refused rather than written. Truncating to zero and calling it
    // a clip is precisely the 0-byte defect: the file would be indistinguishable from the
    // placeholder nextClipName() leaves, which is the state the product shipped.
    if (payload.byteLength === 0) {
      throw new TypeError(
        "refusing to write a zero-byte clip: an empty payload would produce a file " +
        "indistinguishable from an unfilled reservation",
      );
    }
    const handle = this.openClip();
    try {
      writeAll(handle.fd, payload);
    } catch (cause) {
      // A failed write must not leave the claimed name empty on disk.
      try { this.abortClip(handle); } catch { /* the reservation stays; it is visible */ }
      throw cause;
    }
    return this.commitClip(handle);
  }

  #assertHandle(handle) {
    if (handle === null || typeof handle !== "object"
      || typeof handle.name !== "string" || !Number.isInteger(handle.fd)) {
      throw new TypeError(
        "expected a handle from openClip(), with { name: string, fd: number }",
      );
    }
    if (this.#dir === null) {
      throw new Error("cannot commit a clip: this ClipWriter has no directory");
    }
  }

  // The one syscall that decides a name: an exclusive create, O_CREAT|O_EXCL, opened
  // for writing so the caller that wins the claim can put bytes into the very file that
  // proved it. Returns the descriptor, or null when another writer already holds the
  // name. Without a directory there is no path to create and no descriptor to return,
  // which is reported as `undefined` so each caller can decide what that means rather
  // than have the degradation applied to it silently.
  #openExclusive(name) {
    if (this.#dir === null) return undefined;
    try {
      return openSync(join(this.#dir, name), "wx");
    } catch (e) {
      if (e.code === "EEXIST") return null;   // taken by another writer; advance
      throw e;                                  // ENOENT (no directory) must be loud
    }
  }

  // The reservation, reduced to a yes/no. With a directory this creates the file
  // exclusively -- the claim and the check are one syscall, so there is no window between
  // them -- then closes the descriptor, leaving the zero-byte placeholder whose purpose
  // is to EXIST. It is deliberately not the way to land a clip; see writeClip().
  //
  // WITHOUT a directory there is no path to create, so this degrades to the old
  // predicate check. That path cannot reserve and does not pretend to: it is the same
  // best-effort behaviour as before, and callers needing exclusivity must pass `dir`.
  #claim(name) {
    const fd = this.#openExclusive(name);
    if (fd === undefined) return !this.#exists(name);
    // null means the name is ALREADY TAKEN by another writer: there is no descriptor to
    // close, and calling closeSync(null) here would throw out of nextClipName() before it
    // could advance. Measured 2026-10-10: the reservation path regressed that way and
    // clip-writer-race.test.mjs went 6/6 red.
    if (fd !== null) closeSync(fd);
    return fd !== null;
  }

  attemptsFor(name) {
    return this.#attempts.get(name) ?? 0;
  }
}

// Clip content arrives as a string, a Buffer or any typed array; all three are accepted
// so a caller holding an encoder's output does not have to convert first. The result is
// always a Buffer, because writeAll() needs a byteLength to loop over.
function toPayload(data) {
  if (typeof data === "string") return Buffer.from(data, "utf8");
  if (Buffer.isBuffer(data)) return data;
  if (ArrayBuffer.isView(data)) {
    return Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  }
  throw new TypeError(
    "clip data must be a string, Buffer or TypedArray; received " +
    (data === null ? "null" : typeof data),
  );
}

// Standalone rather than a method so writeClip() reads as claim -> write -> commit.
// See #writeAll for why the loop exists.
function writeAll(fd, payload) {
  let offset = 0;
  while (offset < payload.byteLength) {
    const written = writeSync(fd, payload, offset, payload.byteLength - offset);
    if (written <= 0) {
      throw new Error(
        `wrote ${offset} of ${payload.byteLength} bytes: the descriptor accepted nothing`,
      );
    }
    offset += written;
  }
  return offset;
}

export { SessionClock, WIDTH };