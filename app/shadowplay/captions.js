// Captions over a clip. HIGHLIGHTS-AI.md is the spec.
// The rule this file enforces: a caption is TIMESTAMPED against the clip it
// belongs to, and a clip with no captions is a valid clip, not a failure. The
// AI may be slow or absent; capture never waits for it.
import { SavePath } from "./save-path.js";

export const MAX_CAPTION_MS = 60000;

export class CaptionTrack {
  #clip;
  #rows;
  #path;

  constructor({ clip, savePath } = {}) {
    if (typeof clip !== "string" || clip.length === 0) {
      throw new TypeError("captions need a clip name");
    }
    this.#clip = clip;
    this.#rows = [];
    this.#path = savePath ?? new SavePath();
  }

  get clip() { return this.#clip; }
  get count() { return this.#rows.length; }

  add(text, atMs) {
    if (typeof text !== "string" || text.trim().length === 0) {
      throw new TypeError("caption text cannot be empty");
    }
    if (!Number.isFinite(atMs) || atMs < 0) {
      throw new RangeError("atMs must be a non-negative number");
    }
    if (atMs > MAX_CAPTION_MS) {
      throw new RangeError(`caption at ${atMs}ms exceeds the ${MAX_CAPTION_MS}ms cap`);
    }
    const row = { text: text.trim(), atMs };
    this.#rows.push(row);
    return row;
  }

  // Ordered, and never overlapping. Two captions at the same instant would make
  // the subtitle file ambiguous.
  ordered() {
    return [...this.#rows].sort((a, b) => a.atMs - b.atMs);
  }

  // Captions travel through the one writer, like everything else.
  //
  // WHAT IS HANDED TO save(), MEASURED BEFORE THIS CHANGE: text.length, a character
  // count, with `text` sitting unused one line above. save() refuses a number because
  // a length is not content, and it was right to: there is no caption file behind the
  // number 7. So the sidecar is the TEXT itself -- the exact bytes a player would read
  // beside the clip -- and the character count is no longer mistaken for the payload.
  //
  // The text is not re-encoded and not summarised on the way out. What goes through the
  // writer is byte-for-byte what ordered() produced, which is what makes the sidecar
  // readable by whatever consumes it later.
  sidecar() {
    if (this.#rows.length === 0) return null;   // a clip without captions is valid
    const text = this.ordered()
      .map((r) => `${Math.round(r.atMs)}\t${r.text}`)
      .join("\n");
    return this.#path.save("highlights", text);
  }
}