// Overlay hotkeys. Two rules from OVERLAY-HOTKEYS.md this file implements:
//   - hotkeys still fire with the overlay disabled (INTEGRATION-PLAN L130).
//   - a debounce rule gates repeated presses (SCREENSHOTS-RECORDINGS L26).
// The overlay is a VIEW. Disabling it must not disable capture.
import { ReplayRing } from "./replay-ring.js";

export const DEFAULT_DEBOUNCE_MS = 250;

export class HotkeyRouter {
  #ring;
  #debounce;
  #overlayOn;
  #last;
  #log;
  #onRefusal;

  // `onRefusal` is the recorder the composition root (index.js) injects. See
  // press() for why a refusal is both recorded AND re-thrown.
  constructor({ ring, debounceMs = DEFAULT_DEBOUNCE_MS, overlayOn = true, onRefusal = null } = {}) {
    if (!(debounceMs >= 0)) throw new RangeError("debounceMs must be >= 0");
    if (onRefusal !== null && typeof onRefusal !== "function") {
      throw new TypeError("onRefusal must be a function or null");
    }
    this.#ring = ring ?? new ReplayRing();
    this.#debounce = debounceMs;
    this.#overlayOn = overlayOn;
    this.#last = new Map();
    this.#log = [];
    this.#onRefusal = onRefusal;
  }

  // Presentation only. Capture is unaffected by design, not by accident.
  setOverlay(on) { this.#overlayOn = Boolean(on); return this.#overlayOn; }
  get overlayOn() { return this.#overlayOn; }

  #debounced(key, nowMs) {
    const last = this.#last.get(key);
    if (last !== undefined && nowMs - last < this.#debounce) return true;
    this.#last.set(key, nowMs);
    return false;
  }

  // ASYNC because instantReplay is async: the delivery gate must be able to REFUSE a
  // clip that does not cover its own clock, and a refusal cannot be expressed by a
  // synchronous return value.
  //
  // WHAT A REFUSAL DOES -- the decision this route owes the caller, stated once:
  // it is BOTH RECORDED and SURFACED. Neither alone is correct.
  //
  //   Surface only (what this did before): the caller learns the press failed,
  //   but nothing in the product records it. SavePath exists so "a failed save
  //   must be visible -- silently writing nothing is indistinguishable from a
  //   crash" (save-path.js:253), and an unrecorded refusal is exactly that
  //   silence. A user who pressed F9 nine times and got nothing has no way to
  //   tell a broken capture from a key that did not register.
  //
  //   Record only: the product knows, but the caller is handed a value that
  //   looks like success. The hotkey that produced nothing would return a
  //   normal action object, which is the stale clip this method was written to
  //   avoid.
  //
  //   So: record through the injected onRefusal, then RE-THROW the original
  //   error unchanged. Recording never mutates or swallows what the caller
  //   sees -- `cause` and the error identity both survive, and a recorder that
  //   throws cannot mask the real refusal.
  async press(key, nowMs = 0) {
    if (typeof key !== "string" || key.length === 0) {
      throw new TypeError("hotkey must be a non-empty string");
    }
    if (this.#debounced(key, nowMs)) {
      this.#log.push({ key, at: nowMs, action: "debounced" });
      return { action: "debounced" };
    }
    let action;
    switch (key) {
      case "f9": {
        // the moment the user presses it: cut on an IDR and remux.
        // If the ring refuses because the clip cannot cover its clock, that refusal
        // is recorded and then propagates to the caller.
        let clip;
        try {
          clip = await this.#ring.instantReplay();
        } catch (err) {
          this.#recordRefusal(err, { key, nowMs, route: "instant-replay" });
          throw err;
        }
        action = { action: "instant-replay", clip };
        break;
      }
      case "f10":
        action = { action: "toggle-recording" };
        break;
      default:
        action = { action: "unbound", key };
    }
    // overlayOn is recorded but never consulted: the hotkey works either way.
    this.#log.push({ key, at: nowMs, ...action, overlayOn: this.#overlayOn });
    return action;
  }

  // The recorder, defended. A refusal whose RECORDING throws must still reach
  // the caller as the original refusal: the recorder is an observer of the
  // failure, never its replacement. A recorder that is absent or broken
  // degrades to "not recorded", which is why it is injected rather than assumed.
  #recordRefusal(err, context) {
    if (this.#onRefusal === null) return;
    try {
      this.#onRefusal(err, context);
    } catch {
      // Swallowed deliberately, and only here: the caller below receives the
      // REAL error. A recorder's own bug must not replace the diagnosis.
    }
  }

  history() { return this.#log.map((e) => ({ ...e })); }
}