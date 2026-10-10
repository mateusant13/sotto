// First line of the ShadowPlay clone. Session-scoped sequence numbers.
// SCREENSHOTS-RECORDINGS.md L207-214: the counter must never reach 10000 within
// a session, so that a lexicographic sort of clip names equals a chronological one.
// ESM because H:\sotto\app\package.json declares "type": "module".
export const WIDTH = 4;
export const CEILING = 10000;

export function format(n) {
  if (!Number.isInteger(n)) throw new TypeError("sequence must be an integer");
  if (n < 0 || n >= CEILING) {
    throw new RangeError(`sequence ${n} outside [0, ${CEILING})`);
  }
  return String(n).padStart(WIDTH, "0");
}

export class SessionClock {
  #next = 0;
  constructor({ ceiling = CEILING } = {}) {
    this.ceiling = ceiling;
  }
  nextName() {
    if (this.#next >= this.ceiling) {
      throw new RangeError(
        `session clock exhausted at ${this.ceiling}; reset scope is undecided`
      );
    }
    return format(this.#next++);
  }
}
