// Broadcast transport. BROADCAST-OBS.md is the spec.
// The rule this file exists to enforce: a transport is chosen and probed BEFORE
// the stream starts, and if the probe fails the user is told. A broadcast that
// silently produces nothing is worse than one that refuses to start.
export const TRANSPORTS = ["rtmp", "srt", "whip"];

export class Broadcast {
  #transport;
  #target;
  #probed;
  #live;

  constructor({ transport, target } = {}) {
    if (!TRANSPORTS.includes(transport)) {
      throw new RangeError(`unsupported transport: ${transport}`);
    }
    if (typeof target !== "string" || target.length === 0) {
      throw new TypeError("broadcast needs a target");
    }
    this.#transport = transport;
    this.#target = target;
    this.#probed = false;
    this.#live = false;
  }

  get transport() { return this.#transport; }
  get live() { return this.#live; }

  // Probing is mandatory and separate from going live. Going live without a
  // probe is the bug this class exists to prevent.
  async probe(probeFn) {
    if (typeof probeFn !== "function") {
      throw new TypeError("probe needs a function");
    }
    const ok = await probeFn(this.#transport, this.#target);
    this.#probed = ok === true;
    if (!this.#probed) {
      throw new Error(`probe failed for ${this.#transport}: refusing to stream`);
    }
    return true;
  }

  async start(probeFn) {
    if (!this.#probed) await this.probe(probeFn);
    this.#live = true;
    return { transport: this.#transport, live: true };
  }

  stop() { this.#live = false; return this.#live; }
}