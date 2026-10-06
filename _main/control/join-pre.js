/**
 * Fragment joining. The streaming model emits one or two words per ~0.56 s hop,
 * so the raw stream reads "checked / has / under / o / so / is". Measured
 * 2026-10-06: 29 of those arrived in 40 s and none of them is a sentence.
 *
 * A line is therefore emitted when the PHRASE closes — terminal punctuation, a
 * silence gap longer than PHRASE_GAP_MS (the model stopped producing), or a hard
 * cap on length/age so a run-on can never grow unbounded. Nothing here invents
 * text: the joined line is the fragments, concatenated, in arrival order.
 */
const PHRASE_GAP_MS = 1200;
const PHRASE_MAX_MS = 6000;
const PHRASE_MAX_CHARS = 90;
const PHRASE_TERMINAL = /[.!?\u2026]$/;

let phrase = { text: '', openedAt: 0, lastAt: 0 };
let phraseTimer = 0;

/** A phrase must close on TIME, not only on the next event. Measured 2026-10-06:
 *  a sparse stream (3 fragments, then silence) left its text in this buffer and
 *  NOTHING was rendered — no further fragment and no status arrived to flush it,
 *  so the owner saw nothing while the log held `text="g"`, `"gen"`, `"s"`. */
function armPhraseTimer() {
  clearTimeout(phraseTimer);
  phraseTimer = setTimeout(() => {
    phraseTimer = 0;
    flushPhrase();
  }, PHRASE_GAP_MS);
}

/** Emit the accumulated phrase as one line, if there is one. */
function flushPhrase() {
  clearTimeout(phraseTimer);
  phraseTimer = 0;
  const text = phrase.text.trim();
  phrase = { text: '', openedAt: 0, lastAt: 0 };
  if (text) addCaption(text);
  return text;
}

/** Accumulate one raw fragment; render only when the phrase closes. */
function ingestFragment(fragment) {
  if (!fragment) return;
  const now = Date.now();
  if (phrase.text && now - phrase.lastAt > PHRASE_GAP_MS) flushPhrase();
  if (!phrase.text) phrase.openedAt = now;
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
}
