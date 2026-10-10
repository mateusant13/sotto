// The invariant the whole design hangs on (INTEGRATION-PLAN):
//   every stored clip is REMUXED from already-encoded bytes, starts on an IDR,
//   and is NEVER re-encoded.
// So there are exactly two operations here: encode (once, live) and remux
// (byte copy, at save time). Nothing else may touch the payload.
export const FRAME_TYPES = { IDR: 0, P: 1 };

export class Encoder {
  #gop;
  #frames;
  #log;

  constructor({ gopSize = 60 } = {}) {
    if (!Number.isInteger(gopSize) || gopSize < 1) {
      throw new RangeError("gopSize must be a positive integer");
    }
    this.#gop = gopSize;
    this.#frames = [];
    this.#log = [];
  }

  get gopSize() { return this.#gop; }
  get encoded() { return this.#frames.length; }

  // Encoding happens exactly once, here, live. Frame 0 is an IDR by definition.
  encodeFrame(index, payloadBytes) {
    if (!Number.isInteger(payloadBytes) || payloadBytes < 0) {
      throw new RangeError("payloadBytes must be a non-negative integer");
    }
    const type = index % this.#gop === 0 ? FRAME_TYPES.IDR : FRAME_TYPES.P;
    const frame = { index, type, bytes: payloadBytes };
    this.#frames.push(frame);
    this.#log.push({ op: "encode", index, type, bytes: payloadBytes });
    return frame;
  }

  // The save-time operation. A byte copy. It must not call encodeFrame, and the
  // log is how a test proves it did not.
  remux(fromIndex) {
    const slice = this.#frames.filter((f) => f.index >= fromIndex);
    if (slice.length === 0) throw new RangeError("nothing to remux at that index");
    if (slice[0].type !== FRAME_TYPES.IDR) {
      throw new RangeError(`remux from ${fromIndex} would not start on an IDR`);
    }
    const bytes = slice.reduce((a, f) => a + f.bytes, 0);
    this.#log.push({ op: "remux", fromIndex, frames: slice.length, bytes });
    return { frames: slice.length, bytes, startType: slice[0].type };
  }

  operations() { return this.#log.map((e) => e.op); }
  encodeCount() { return this.#log.filter((e) => e.op === "encode").length; }
}