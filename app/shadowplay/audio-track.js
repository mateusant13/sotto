// The audio track, wired into the one save path.
// AUDIO.md section 4: the mix domain is decided by whether the sources are
// correlated, and that decision changes whether the result clips. This module
// makes that decision explicit and never lets the app record its own output
// twice by accident: capturing an app that already mixes the sources is the
// correlated case, and it is the one that clips.
import { mix, toDbFS, safeGain, HEADROOM_DB } from "./audio-mix.js";
import { SavePath } from "./save-path.js";

export class AudioTrack {
  #rate;
  #channels;
  #sources;
  #path;

  constructor({ rate = 48000, channels = 2, sources = [], savePath } = {}) {
    if (!Number.isInteger(rate) || rate <= 0) {
      throw new RangeError("rate must be a positive integer");
    }
    if (!Number.isInteger(channels) || channels <= 0) {
      throw new RangeError("channels must be a positive integer");
    }
    if (!Array.isArray(sources) || sources.length === 0) {
      throw new RangeError("a track needs at least one source");
    }
    this.#rate = rate;
    this.#channels = channels;
    this.#sources = sources;
    this.#path = savePath ?? new SavePath();
  }

  get rate() { return this.#rate; }
  get channels() { return this.#channels; }

  // Sources sharing a clock are correlated. Sources with independent clocks are
  // not. This is the whole difference between the two summation domains.
  correlated() {
    const clocks = new Set(this.#sources.map((s) => s.clock ?? "independent"));
    return clocks.size === 1;
  }

  // Returns the mix and whether it clipped. Never returns a clipped mix silently.
  render(gains = 1) {
    const comps = this.#sources.map((s) => s.amplitude * gains);
    const out = mix(comps, { correlated: this.correlated() });
    const applied = out.linear * safeGain(this.correlated());
    return {
      linear: applied,
      dbfs: toDbFS(applied),
      unclipped: applied < 1,
      correlated: out.correlated,
      headroomDb: HEADROOM_DB,
    };
  }

  // The audio goes through the same single writer as video (Phase 6, L129).
  //
  // TWO ARGUMENTS, AND WHY THE SECOND ONE IS NOT OPTIONAL.
  //
  // MEASURED BEFORE THIS CHANGE: attach(frames) passed `frames` -- a frame COUNT -- to
  // save(), which refuses a number because a length is not content. There is no audio
  // behind the number 4800. The count survives as an argument because it is a real,
  // validated property of the audio (and this module already refuses a non-positive
  // one with a RangeError, which is a guard worth keeping), but the clip's CONTENT now
  // has to arrive with it.
  //
  // `audio` is the encoded audio the caller is holding -- a Buffer or TypedArray from
  // the encoder. It is passed straight through: this module mixes and reports levels,
  // it does not encode, so re-serialising the payload here would be inventing bytes
  // nobody produced.
  attach(frames, audio) {
    if (!Number.isInteger(frames) || frames <= 0) {
      throw new RangeError("frames must be a positive integer");
    }
    if (!isPayload(audio)) {
      throw new TypeError(
        "attach() needs the audio's bytes, not just a frame count: received " +
        (audio === null ? "null" : typeof audio) +
        ". A frame count describes audio that nobody has, so it cannot be written.",
      );
    }
    return this.#path.save("hotkey", audio);
  }
}

// Is this something the writer can put on disk? Mirrors ClipWriter's own acceptance --
// string, Buffer or any TypedArray -- so this guard refuses at the CALLER with a message
// about audio, rather than letting the number travel one layer deeper before save()
// refuses it for a reason that does not mention audio at all.
function isPayload(value) {
  return typeof value === "string" || ArrayBuffer.isView(value);
}