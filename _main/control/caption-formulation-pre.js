// NEGATIVE CONTROL — the pre-change caption pipeline.
//
// This is the join that lived in `app/electron/panel.js` before this work,
// wrapped in the SAME interface the real module exposes, so
// `_main/join-harness-control.js` can drive the IDENTICAL arms against it.
//
// It exists to answer one question with a run instead of an argument: do the
// new arms actually go RED on the old code, or do they merely describe
// behaviour the old code already had? A gate that cannot go red is not a gate.
//
// The implementation below is the old source verbatim — `PHRASE_GAP_MS = 1200`
// wall-clock, no audio awareness, no revision detection, no punctuation pass —
// with `formulate` reduced to identity and `describeReadiness` reduced to the
// placeholder-sequence behaviour the panel really had.

'use strict';

let NOW = 1000000;

const PHRASE_GAP_MS = 1200;
const PHRASE_MAX_MS = 6000;
const PHRASE_MAX_CHARS = 90;
const PHRASE_TERMINAL = /[.!?…]$/;

let phrase = { text: '', openedAt: 0, lastAt: 0 };
let phraseTimer = 0;

/** The old sink: every flushed phrase becomes one rendered line, verbatim. */
function addCaption(text) {
  if (!text) return false;
  committedLinesPre.push(text);
  return true;
}

const committedLinesPre = [];
let provisionalTextPre = '';

function armPhraseTimer() {
  clearTimeout(phraseTimer);
  phraseTimer = setTimeout(() => {
    phraseTimer = 0;
    flushPhrase();
  }, PHRASE_GAP_MS);
}

function flushPhrase() {
  clearTimeout(phraseTimer);
  phraseTimer = 0;
  const text = phrase.text.trim();
  phrase = { text: '', openedAt: 0, lastAt: 0 };
  if (text) addCaption(text);
  return text;
}

function ingestFragment(fragment) {
  if (!fragment) return;
  const now = NOW;
  if (phrase.text && now - phrase.lastAt > PHRASE_GAP_MS) flushPhrase();
  if (!phrase.text) phrase.openedAt = now;
  // The old line: append unconditionally. No audio, no revision, no dedupe.
  phrase.text = phrase.text ? `${phrase.text} ${fragment}` : fragment;
  phrase.lastAt = now;
  if (
    PHRASE_TERMINAL.test(phrase.text) ||
    phrase.text.length >= PHRASE_MAX_CHARS ||
    now - phrase.openedAt >= PHRASE_MAX_MS
  ) {
    flushPhrase();
    return;
  }
  armPhraseTimer();
  provisionalTextPre = phrase.text;
}

/**
 * The old pipeline had NO formulation pass: whatever the model said is what
 * the panel rendered. `formulate` is therefore the identity, and that is the
 * whole point — arm 9 must fail here.
 */
function formulate(text) {
  return String(text == null ? '' : text).trim();
}

/** The old panel showed a SEQUENCE of placeholders, not one state. */
function describeReadiness() {
  return { state: 'unknown', title: 'Waiting for audio', body: 'Nothing is being transcribed yet.' };
}

function createEngine(options) {
  const onCommit = options.onCommit;
  const onProvisional = options.onProvisional;

  committedLinesPre.length = 0;
  provisionalTextPre = '';

  return {
    /**
     * The old engine had no `meta`: audio position was thrown away by the
     * panel, which is precisely why the 1200 ms wall-clock rule was the only
     * boundary available and why it never fired.
     */
    ingest(text) {
      const before = committedLinesPre.length;
      ingestFragment(String(text == null ? '' : text).trim());
      for (let i = before; i < committedLinesPre.length; i += 1) {
        onCommit(committedLinesPre[i], 'pre');
      }
      onProvisional(provisionalTextPre || phrase.text || '', true);
    },
    flush() {
      flushPhrase();
    },
    visible: () => phrase.text,
    state: () => ({ committed: [], provisional: phrase.text ? phrase.text.split(/\s+/) : [] }),
  };
}

/** Test seam: the arms advance this instead of real time. */
function advance(ms) {
  NOW += ms;
}

module.exports = {
  createEngine,
  formulate,
  describeReadiness,
  advance,
  agreedPrefixLength: (a, b) => {
    const n = Math.min(a.length, b.length);
    let i = 0;
    while (i < n && a[i] === b[i]) i += 1;
    return i;
  },
  words: (t) => String(t == null ? '' : t).trim().split(/\s+/).filter(Boolean),
  SENTENCE_GAP_S: 1200 / 1000,
  SENTENCE_MAX_CHARS: PHRASE_MAX_CHARS,
  COMMIT_MAX_HOLD_MS: PHRASE_GAP_MS,
  READY_SECONDS_MEASURED: 6.4,
};
