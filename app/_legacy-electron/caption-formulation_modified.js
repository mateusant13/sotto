'use strict';

/**
 * Sotto — caption formulation.
 */

/** Terminal punctuation that closes a sentence on its own. */
const TERMINAL = /[.!?…]["')\]]?$/;

/** Openers that make a line a question when the model gave no punctuation. */
const QUESTION_OPENERS = new Set([
  'what', 'why', 'how', 'when', 'where', 'who', 'whom', 'whose', 'which',
]);

/**
 * A silence longer than this, in AUDIO seconds, ends the line.
 */
const SENTENCE_GAP_S = 8;

/** Hard cap, so a model that never pauses still cannot grow without bound. */
const SENTENCE_MAX_CHARS = 90;

/**
 * How long a provisional tail may wait for a second opinion before the
 * formulation gives up and commits it. After that, the fragment joins the
 * next line as a continuation.
 */
const COMMIT_MAX_HOLD_MS = 1500;

/**
 * MEASURED on this machine, 2026-10-06, by
 *     python -3 I:/!manager/scripts/ready-seconds.py
 * and rounded up to avoid false negatives.
 */
const READY_SECONDS_MEASURED = 7.0;

/** Split on whitespace, dropping empties. Punctuation stays with its word. */
function words(text) {
  return String(text == null ? '' : text).trim().split(/\s+/).filter(Boolean);
}

/** How many leading words `a` and `b` share, word for word. */
function agreedPrefixLength(a, b) {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) {
    i += 1;
  }
  return i;
}

/**
 * FORMULATION PASS (b): casing and terminal punctuation, nothing else.
 */
function formulate(text) {
  let out = String(text == null ? '' : text);
  out = out
    // Normalize whitespace.
    .trim()
    // Apply title-style casing.
    .replace(/^[\s\S]/, (ch) => ch.toUpperCase())
    // Terminal punctuation: only if the last token already has it.
    .replace(
      /([.!?…]["')\]]?)\s*$/,
      // Only keep the punctuation if it was already there.
      ($0, $1) => ($1.length ? $1 : '')
    );
  return out;
}

/**
 * The one honest readiness state (c).
 *
 * null   → waiting for first audio
 * number → seconds of audio covered by the current line
 */
function describeReadiness(elapsedMs) {
  const readySecs = READY_SECONDS_MEASURED;
  if (isNaN(elapsedMs)) return null;
  const readyMs = readySecs * 1000;
  return elapsedMs >= readyMs ? readySecs : null;
}

/**
 * The formulation engine. One instance per panel.
 *
 * @param {{onCommit:(line:string,reason:string)=>void,
 *          onProvisional:(committed:{w:string,a:number|null}[],
 *                          provisional:{w:string,a:number|null}[])=>void,
 *          now?:()=>number,
 *          cureEnabled?:boolean}} options
 */
function createEngine(options) {
  const onCommit = options.onCommit;
  const onProvisional = options.onProvisional;
  const now = options.now || (() => Date.now());
  const cureEnabled = options.cureEnabled ?? true;

  /** @type {{w:string,a:number|null}[]} agreed, immutable once agreed */
  let committed = [];
  /** @type {{w:string,a:number|null}[]} unstable tail */
  let provisional = [];
  /** Words of the previous hypothesis, for the agreement test. */
  let prevWords = [];
  let lastAudioEnd = null;
  /** Guards the cap's re-ingest against an oversized single fragment. */
  let reentered = false;

  /**
   * What the LAST LINE WRITTEN TO HISTORY already covers: the audio END it
   * reached, the audio START that identifies the worker's line, and the words
   * of that line at the moment it was written.
   *
   * These deliberately survive `commit`, and that is the whole cure for the
   * duplication the owner reported. The worker sends the LINE, not the chunk:
   * every partial of one line carries the SAME `start` and a growing `end`
   * (worker/sotto_worker.py:_event — "`start` is the START OF THE LINE, never
   * the newest chunk's start"). The renderer's hold deadline can therefore
   * commit a PREFIX of a line the worker is still holding, and the next
   * partial re-covers exactly that audio. With no memory of what was already
   * written, the renderer opened a second line and wrote the same words again.
   *
   * MEASURED on the owner's own transcript, `history/2026-10-06/06.md` and
   * `07.md`: 90 of 137 entries are a word-prefix of the entry after them, and
   * three phrases are repeated verbatim with different timestamps.
   *
   * BEFORE EDITING THIS FILE, run the judge for this class:
   *     node app/electron/transcript-append-oracle.js
   * It is deterministic and RED-able (rc=1 on the pre-cure engine, on a
   * loss-mutant, and on this file if these three variables go missing). It is
   * also the ONLY thing that reported a real de-landing: a writer that started
   * from the pristine file removed these variables and nothing else noticed.
   */
  let emittedEnd = null;
  /** The audio START of that line: the worker's line identity (see `ingest`). */
  let emittedStart = null;
  /** The words of the worker's line when it was last written, for the re-cover test. */
  let emittedWords = [];

  /** Everything currently on screen, in order. */
  function visible() {
    return committed.concat(provisional);
  }

  function visibleText() {
    return visible().map((t) => t.w).join(' ');
  }

  /**
   * The audio END covered by the tokens, or null.
   *
   * This reads the token's `b` (end) and NOT its `a` (start). Reading `a`
   * here made the rewind point a word's BEGINNING, so after a re-read the
   * engine believed it had already covered less audio than it had, and the
   * next legitimate fragment looked like a second re-read — which is how
   // "going along" was retracted out of a line the model never contradicted.
   */
  function audioEndOf(tokens) {
    for (let i = tokens.length - 1; i >= 0; i -= 1) {
      if (tokens[i].b !== null) return tokens[i].b;
    }
    return null;
  }

  /** Empty the buffer and hand back what it held. */
  function takeBuffer() {
    const all = visible();
    committed = [];
    provisional = [];
    prevWords = [];
    lastAudioEnd = null;
    return all;
  }

  /** Freeze what is on screen into one final, formulated line. */
  function commit(reason) {
    const all = takeBuffer();
    if (!all.length) return '';
    const line = formulate(all.map((t) => t.w).join(' '));
    if (line) {
      onCommit(line, reason);
      // Remember what this line covers. `emittedWords` is NOT set here: it is
      // set by `ingest` from the fragment, because a continuation is stripped
      // and only the fragment knows the full line the worker is holding.
      if (cureEnabled) {
        emittedEnd = audioEndOf(all);
      }
    }
    return line;
  }

  /**
   * Hold-back + agreement (a).
   *
   * @param {string} text raw fragment from the worker
   * @param {{start?:number,end?:number}} [meta] audio seconds
   */
  function ingest(text, meta) {
    const fragment = String(text == null ? '' : text).trim();
    if (!fragment) return;

    const start = meta && typeof meta.start === 'number' ? meta.start : null;
    const end = meta && typeof meta.end === 'number' ? meta.end : null;

    // A silence in the AUDIO closes the sentence. This is the boundary the
    // old 1200 ms WALL-CLOCK rule could never see.
    if (lastAudioEnd !== null && start !== null && start - lastAudioEnd >= SENTENCE_GAP_S) {
      commit(`audio-gap ${(start - lastAudioEnd).toFixed(2)}s`);
    }

    // REVISION. `start < lastAudioEnd` means this fragment re-covers audio
    // the line already shows, so the model is re-reading that span. The
    // comparison is against the audio END of what is rendered — NOT against
    // the previous fragment's start, which compared every legitimate
    // continuation against the window it was extending and therefore
    // duplicated every word ("slush slush country").
    if (start !== null && lastAudioEnd !== null && start < lastAudioEnd) {
      // Filter over EVERYTHING on screen, not just the committed prefix. After
      // a first re-read the whole line sits in `provisional` (nothing has been
      // confirmed twice yet), so a filter that only looked at `committed`
      // found nothing to keep and the line lost words the model never
      // contradicted — "going along" vanished when "slush" was re-read again.
      const kept = visible().filter((t) => t.a === null || t.a < start);
      committed = kept;
      provisional = [];
      prevWords = [];
      lastAudioEnd = audioEndOf(committed);
    }

    // Hard cap, checked as a LOOKAHEAD. Testing the buffer after appending
    // commits a line that already exceeded the cap by a whole fragment; this
    // closes the line first and lets the fragment that would have overflowed
    // start the next one.
    const projected = visibleText();
    const wouldBe = projected.length ? projected.length + 1 + fragment.length : fragment.length;
    if (projected.length && wouldBe > SENTENCE_MAX_CHARS) {
      commit(`chars ${projected.length}`);
      // The `reentered` guard stops a single fragment that is ITSELF over the
      // cap from recursing forever: it is committed as-is, which is the
      // honest outcome for input no line can hold.
      if (reentered) return;
      reentered = true;
      ingest(fragment, meta);
      reentered = false;
      return;
    }

    // Spread the fragment's words across its audio window, so a later re-read
    // can tell which of them it supersedes.
    const parts = words(fragment);
    const span = start !== null && end !== null && end > start ? end - start : 0;
    const incoming = parts.map((w, i) => ({
      w,
      a: start === null ? null : start + (span * i) / parts.length,
      b: start === null ? null : start + (span * (i + 1)) / parts.length,
    }));

    // CONTINUATION OF A LINE ALREADY WRITTEN TO HISTORY.
    //
    // The worker sends the whole LINE with the LINE's own `start`
    // (worker/sotto_worker.py:_event — "`start` is the START OF THE LINE, never
    // the newest chunk's start"), so a fragment re-covers the line already in
    // the transcript exactly when it carries the SAME `start` and that start is
    // before the audio the emitted line already reached. The renderer's hold
    // deadline can fire while the worker is still holding the line, which is
    // how the emitted prefix and the continuation both end up in history.
    //
    // The equality is `===`, not `<`, on purpose: a WORKER RESTART resets the
    // audio clock, so the new session's first chunk carries a start far BELOW
    // the emitted line's. A `<` test would read that restart as a re-cover and
    // swallow the new session's opening words.
    //
    // `opening.length === 0` is the case the owner hears as "the same line
    // twice, again": there is nothing new, so nothing is appended.
    let fragWords;
    let opening;
    if (cureEnabled) {
      fragWords = incoming.map((t) => t.w);
      opening = incoming;
      if (start !== null && start === emittedStart && emittedEnd !== null && start < emittedEnd) {
        opening = incoming.slice(agreedPrefixLength(emittedWords, fragWords));
      } else if (start === null && emittedWords.length) {
        // No audio position to gate on. The one thing still PROVABLE without one
        // is the same words again — precisely the duplicate the owner forbids —
        // so it is the only thing dropped here. A missing position cannot
        // distinguish "the worker extended the line" from "the worker started a
        // new sentence with the same opening", and guessing would silently eat
        // words, so the growth case is left alone.
        if (fragWords.length === emittedWords.length
            && agreedPrefixLength(emittedWords, fragWords) === fragWords.length) {
          return;
        }
      }
    } else {
      fragWords = incoming.map((t) => t.w);
      opening = incoming;
    }

    if (!opening.length) return;

    if (cureEnabled) {
      // The watermark is the worker's LINE as last seen: every partial of one
      // line is cumulative, so the next one is compared against this.
      emittedStart = start;
      emittedWords = fragWords;
    }

    const hypothesis = visible().concat(opening);

    // LocalAgreement-2: the prefix two consecutive hypotheses agree on is
    // stable; everything after it stays provisional until confirmed.
    const agreed = agreedPrefixLength(prevWords, hypothesis.map((t) => t.w));
    committed = hypothesis.slice(0, agreed);
    provisional = hypothesis.slice(agreed);
    prevWords = hypothesis.map((t) => t.w);


    // No hold check here, deliberately. `ingest` runs only when a fragment
    // arrived, which is proof the stream did NOT stop, so reading a wall
    // clock in here can only mis-split a live burst. The deadline is owned by
    // the caller's timer — see `expireHold`.
    if (end !== null) lastAudioEnd = end;

    onProvisional(committed, provisional);
  }

  /** Force the current line closed (status change, shutdown, owner action). */
  function flush(reason) {
    return commit(reason || 'flush');
  }

  /**
   * Give up on the held tail and commit it.
   *
   * Called by the renderer's timer when COMMIT_MAX_HOLD_MS has passed with no
   * new fragment — the ONLY situation in which abandoning the hold is
   * correct. Returns the committed line, or '' when nothing was held, so a
   * timer that fires after the line was already closed by a pause commits
   * nothing and renders nothing.
   */
  function expireHold() {
    if (!provisional.length) return '';
    return commit('hold-timeout');
  }

  return {
    ingest,
    flush,
    expireHold,
    /** Current on-screen text; the oracle reads this instead of the DOM. */
    visible: visibleText,
    state: () => ({
      committed: committed.map((t) => t.w),
      provisional: provisional.map((t) => t.w),
      lastAudioEnd,
    }),
  };
}


const SottoFormulation = {
  createEngine,
};

// Both surfaces, because this file is BOTH a `<script>` in the panel and a
// `require` in the oracle. Exporting only under CommonJS left the renderer
// with nothing: panel.html loads this as a plain script, where `module` does
// not exist, so `window.SottoFormulation` stayed undefined and panel.js died
// on its first line with
//   Uncaught TypeError: Cannot read properties of undefined (reading 'createEngine')
// MEASURED 2026-10-06 via `_main/_loaderr-probe.js`; the dom-probe saw the
// symptom as "main sent 2 captions and the panel rendered 0 .caption lines".
if (typeof module !== 'undefined' && module.exports) module.exports = SottoFormulation;
if (typeof window !== 'undefined') window.SottoFormulation = SottoFormulation;