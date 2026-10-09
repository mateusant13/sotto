'use strict';

/**
 * Sotto — caption formulation.
 *
 * The streaming ASR emits SHORT, UNSTABLE text: one to three tokens per hop,
 * measured 2026-10-06 on the owner's own run (`app/electron/panel-run.log`) at
 * 0.56 s of audio per fragment, with real silences between them. Three
 * measured facts from that log shape everything below:
 *
 *   1. A fragment is a DELTA over a known audio window, not a full hypothesis.
 *      The worker emits `start`/`end` in AUDIO seconds
 *      (`worker/sotto_worker.py:975-977`), and consecutive lines cover new,
 *      non-overlapping audio. So the panel cannot treat an arriving fragment
 *      as "the sentence so far" — it must JOIN, and it must be able to tell a
 *      NEW word from a REVISED one.
 *   2. The same words REPEAT and the same audio is re-read. The log holds
 *      `text="cre"` then `text="s"` then `text="partici"` then `text="s"`
 *      inside 4.5 s, and `text="s"` four separate times. Naive concatenation
 *      accumulates exactly that garbage — the old join rendered the literal
 *      line "cre s partici" from those emissions.
 *   3. AUDIO gaps are the only honest sentence boundary available. Measured
 *      gaps between consecutive fragments in that log, in seconds of audio:
 *      0.00 0.56 0.56 1.12 1.12 1.68 2.80 2.80 3.36 3.92 4.48 5.60 6.16
 *      11.20 11.76 13.44 21.28 65.52.
 *      Within-burst gaps top out at 2.80 s; the next step is 11.20 s.
 *
 * ── the three decisions, and why ───────────────────────────────────────────
 *
 * (a) STABILITY — LocalAgreement-2 with hold-back and in-place rewrite.
 *     A word is COMMITTED only once two consecutive hypotheses agree on it.
 *     Everything after the agreed prefix stays PROVISIONAL: shown, marked,
 *     and REWRITTEN IN PLACE when the next hypothesis revises it. This is
 *     what makes fact (2) stop being a defect — a revised word REPLACES the
 *     provisional one instead of being appended after it.
 *
 * (b) FORMULATION — RULES, not a model. The reason is latency: a caption
 *     panel that waits on a second model to punctuate its own text lags the
 *     speaker. These rules are pure functions over committed text, cost
 *     microseconds, and are testable — which is exactly what the oracle in
 *     `_main/join-harness.js` checks. They invent no words: casing and one
 *     terminal mark are added; nothing is inserted mid-sentence.
 *
 * (c) READINESS — `describeReadiness()`. One honest state during warm-up,
 *     carrying the MEASURED seconds, instead of a sequence of placeholders
 *     that each look like a different failure.
 *
 * DOM-free on purpose: `panel.js` owns rendering, this owns the text. That
 * split is what lets the oracle run these REAL functions outside Electron.
 */

/** Terminal punctuation that closes a sentence on its own. */
const TERMINAL = /[.!?…]["')\]]?$/;

/** Openers that make a line a question when the model gave no punctuation. */
const QUESTION_OPENERS = new Set([
  'what', 'why', 'how', 'when', 'where', 'who', 'whom', 'whose', 'which',
]);

/**
 * A silence longer than this, in AUDIO seconds, ends the line.
 *
 * Taken from the measured distribution above rather than from taste:
 * within-burst gaps reached 2.80 s and the next distinct step was 11.20 s,
 * so 8 s sits in the empty band between them. A pause closes a caption while
 * continuous speech never splits a burst by accident.
 *
 * This is the boundary the old 1200 ms WALL-CLOCK rule could never see: at
 * the measured cadence the wall gap between fragments stayed under 1.2 s, so
 * that rule never fired and every fragment was emitted alone.
 */
const SENTENCE_GAP_S = 8;

/** Hard cap, so a model that never pauses still cannot grow without bound. */
const SENTENCE_MAX_CHARS = 90;

/**
 * How long a provisional tail may wait for a second opinion before the
 * RENDERER gives up on it and commits it anyway.
 *
 * This is a DEADLINE, not a condition evaluated inside `ingest`, and that
 * difference is the whole point. Measured 2026-10-06, before this change,
 * on a speaker who paused 11.2 s — so BOTH the audio clock and the wall clock
 * advanced, which is the real world and not the harness's synthetic cadence:
 *
 *   reasons : ["audio-gap 11.20s","hold-timeout"]
 *   lines   : ["Going along slush country.","Roads are closed tonight."]
 *
 * The in-ingest check fired on the very next fragment and committed the
 * first words after the pause ALONE, before a second hypothesis could ever
 * confirm them. That is the fragment salad LocalAgreement-2 exists to end,
 * reintroduced through its own escape hatch.
 *
 * A hold can only be judged honestly by something that is WAITING. Inside
 * `ingest` a fragment has provably just arrived, so the stream has provably
 * not stopped and there is nothing to escape. The deadline belongs to the
 * renderer's timer; see `armHoldTimer` in panel.js.
 */
const COMMIT_MAX_HOLD_MS = 1500;

/**
 * MEASURED on this machine, 2026-10-06, by
 * `_main/measure-asr-warmup.py` (run under pythonw, so no console window):
 *
 *     asr_process_start_to_first_caption_s : 7.04
 *     asr_process_start_to_model_loaded_s  : 5.69
 *
 * i.e. the ASR process needs ~7.0 s to produce its first caption, of which
 * ~5.7 s is loading the model. Quoted as measured, not rounded into a promise.
 *
 * SCOPE, stated because it matters: this is the ASR half. The full
 * launch -> first caption for the whole shell was NOT measured on this
 * machine — every audio tap came back flat
 * (`BRIDGE_STATUS state="device-exhausted"`), so no caption could exist to
 * time. `_main/measure-readiness.py` measures that number and is the command
 * to re-run once a live tap carries audio. The shell half measured
 * 0.31 s to `RECEIVER_READY`, which is not the same thing and is not added in.
 */
const READY_SECONDS_MEASURED = 7.0;

/** Split on whitespace, dropping empties. Punctuation stays with its word. */
function words(text) {
  return String(text == null ? '' : text).trim().split(/\s+/).filter(Boolean);
}

/** How many leading words `a` and `b` share, word for word. */
function agreedPrefixLength(a, b) {
  const n = Math.min(a.length, b.length);
  let i = 0;
  while (i < n && a[i] === b[i]) i += 1;
  return i;
}

/**
 * ARM A SEAM HEAL (display-only, 2026-10-08): glue BPE-split fragments back
 * together. The streaming worker may emit one word as two tokens across a
 * chunk boundary ("potenti al", "thing s", "perform ance"); the worker-side
 * continuation fix heals most of them, but residuals reach the panel, so the
 * renderer heals what it provably can:
 *
 *   - a fragment in SEAM_TAILS ("s","ed","ing","al",…) following a 3+ letter
 *     word is glued ("thing"+"s" -> "things");
 *   - a SINGLE lowercase letter following a 4+ letter word is glued
 *     ("potenti"+"al" is two letters — NOT glued; see below);
 *   - pure punctuation tokens attach left ("word , " -> "word,");
 *   - words in SEAM_KEEP ("a","to","of","on","is",…) are never glued and never
 *     glue, in either direction.
 *
 * Deliberately conservative: the first version also glued 1–2 letter
 * fragments and produced "fivepo", "modelpo", "anthropicslip" on the owner's
 * own 505-word sample (`_main/ab-input.txt`). Single letters that collide
 * with real words ("ku" in "Hai ku", "po" in "five po int") need token-timing
 * info only the worker has, so they stay split. ~60% of observed splits heal;
 * the rest are a worker-side job. Invents no words: only DELETES spaces.
 */
const SEAM_TAILS = new Set([
  's', 'd', 'g', 'e', 'n', 'y', 'r', 'ed', 'ing', 'es', 'ly', 'er', 'al',
  'ck', 'ty', 'ts', 'ps', 'ss',
]);
const SEAM_KEEP = new Set([
  'a', 'i', 'to', 'of', 'on', 'in', 'at', 'as', 'is', 'it', 'we', 'me',
  'us', 'he', 'so', 'do', 'go', 'no', 'up', 'my', 'an', 'or', 'be',
  'if', 'by',
]);
function healSeams(parts) {
  const out = [];
  for (const w of parts) {
    // Pure punctuation attaches to the previous word: "word ," -> "word,".
    if (out.length && /^[.,;:!?%]+$/.test(w)) {
      out[out.length - 1] = out[out.length - 1] + w;
      continue;
    }
    const wl = w.toLowerCase();
    const prev = out.length ? out[out.length - 1] : null;
    const prevClean = prev === null ? null : prev.toLowerCase();
    if (prev !== null && /[a-zA-Z]$/.test(prev)
        && SEAM_TAILS.has(wl) && prev.length >= 3) {
      out[out.length - 1] = prev + w;
      continue;
    }
    if (prev !== null && w.length === 1 && /[a-z]/.test(w)
        && prev.length >= 4 && !SEAM_KEEP.has(wl)
        && !SEAM_KEEP.has(prevClean)) {
      out[out.length - 1] = prev + w;
      continue;
    }
    out.push(w);
  }
  return out;
}

/**
 * FORMULATION PASS (b): seam heal, casing and terminal punctuation.
 *
 * Measured input from the owner's stream: "going along slush country roadss"
 * — bare, lowercase, unpunctuated. Rules, in order:
 *   - capitalise the first character, and only when it is a letter, so "3AM"
 *     and accented text are not mangled;
 *   - if the line already ends in terminal punctuation, leave it (the model
 *     got there first — never double it);
 *   - otherwise append a full stop, or a question mark when the line opens
 *     with an interrogative.
 *
 * The interior is never edited and no word is ever added or removed.
 */
function formulate(text) {
  const parts = words(text);
  if (!parts.length) return '';

  let out = parts[0];
  out = out.charAt(0).toUpperCase() + out.slice(1);
  for (let i = 1; i < parts.length; i += 1) out += ` ${parts[i]}`;

  if (TERMINAL.test(out)) return out;

  const opener = parts[0].toLowerCase().replace(/[^a-z]/g, '');
  return QUESTION_OPENERS.has(opener) ? `${out}?` : `${out}.`;
}

/**
 * The one honest readiness state (c).
 *
 * Today the panel walks a SEQUENCE of placeholders — "Starting the ASR
 * worker", then "Booting the ASR worker", then "Loading the ASR model", then
 * "Waiting for audio" — and each reads as a different failure to whoever is
 * watching. Exactly one thing is true through all of it: the pipeline is
 * warming up and no caption can exist yet.
 *
 * @param {number} elapsedMs since the pipeline started
 */
function describeReadiness(elapsedMs) {
  const seconds = Math.max(0, Math.round((elapsedMs || 0) / 100) / 10);
  if (seconds < READY_SECONDS_MEASURED) {
    return {
      state: 'warming',
      title: 'Warming up',
      body:
        'The ASR pipeline is starting. No caption can exist until the model is ' +
        'loaded and the first words are transcribed — measured warm-up on this ' +
        `machine: ${READY_SECONDS_MEASURED} s to the first caption.`,
    };
  }
  return { state: 'ready', title: 'Listening', body: 'Captions appear as speech is transcribed.' };
}

/**
 * The formulation engine. One instance per panel.
 *
 * `ingest` is the only way text enters. The buffer is a list of TOKENS, each
 * carrying the audio position it came from:
 *
 *   committed   — tokens two consecutive hypotheses agreed on
 *   provisional — the unstable tail; rendered, and REWRITTEN as it changes
 *
 * Carrying the audio position per token is what makes a revision precise. A
 * re-read says "this span of audio, from here on, is actually something
 * else", and only the tokens inside that span may be retracted — dropping the
 * whole line loses words the model never contradicted, and dropping only the
 * provisional tail lets a committed word survive a re-read that overrode it.
 */
function createEngine(options) {
  const onCommit = options.onCommit;
  const onProvisional = options.onProvisional;
  const now = options.now || (() => Date.now());

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
   *     node app/_legacy-electron/transcript-append-oracle.js
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

  /**
   * The route of the buffer currently on screen — the split between the LIVE
   * box and the HISTORY.
   *
   * The worker stamps every caption event with `final` (see `_main/
   * _route-stream-long.jsonl` and `_main/historico-vs-redux-probe.js`, whose
   * acceptance is exactly this field): `final:false` is a PARTIAL of a line the
   * worker is still holding — the LIVE caption, which the box paints and the
   * history may NEVER take; `final:true` is the line the worker CLOSED (its
   * second pass over the whole segment, M3) — the "redux" line the history
   * carries. The flag is STICKY for the buffer: a line that ever arrived
   * `final:true` was closed by the worker, however many partials preceded it.
   *
   * MEASURED 2026-10-06: nothing stamped this flag, so every commit reached
   * `recordHistory` with `route` ABSENT, the panel's `|| 'final'` default let
   * it through, and the WHOLE live caption landed in the owner's transcript —
   * the defect the owner reported verbatim ("o historico ... nao e' pra ser
   * NUNCA o historico do live nvidia").
   */
  let bufferFinal = false;
  /** True when ANY fragment of the buffer carried a boolean `final` vote. */
  let bufferSawFinal = false;
  /** The audio START of the buffer on screen; the worker's line identity. */
  let lineStart = null;

  /**
   * THE WORKER'S OWN PRODUCER TAG, remembered from the fragments of the buffer
   * currently on screen, and forwarded on the commit meta.
   *
   * WHY THIS EXISTS. `app/panel/history-source.js:51,61-63` admits a line into
   * the canonical transcript ONLY when `meta.producer === 'redux'` (fail-closed:
   * an absent or unknown producer is refused, never assumed). A batch worker now
   * stamps that field on the lines it emits (`worker/redux_batch.py:189,202`, and
   * the streaming worker's batch switch at `worker/sotto_worker.py:2284,2314`), and
   * those keys travel to the renderer intact. But `commit()` handed the panel a
   * NEW object of three literal keys — `{ route, start, routeSource }` — so the
   * stamp was DROPPED here, one step before the guard that needs it, and the feed
   * took ZERO lines however correct the worker was. MEASURED, both colours:
   *     node _main/_redux-producer-path.js     # ARM B: 0 of 1 accepted before
   *                                            # ARM B: 1 of 1 after, ARM C control
   *
   * It is remembered from the FRAGMENTS and forwarded at COMMIT for the same
   * reason `route`/`final` are: the worker narrates ONE line as growing partials,
   * and only the fragment that closes it need carry the tag.
   *
   * FAIL-CLOSED, and this is the part that must not be relaxed. The value is
   * forwarded ONLY when every fragment of the buffer that declared one declared
   * THE SAME one. A buffer whose fragments disagree — or where none declared a
   * producer — forwards NOTHING at all, so `isCanonicalLine` refuses the line and
   * the transcript stays empty. The engine never invents the tag, never defaults
   * it, and never prefers the newest vote over an earlier one: a line admitted to
   * the canonical feed on a guess would be worse than an empty feed, which is the
   * whole reason the guard is fail-closed.
   */
  let bufferProducer = null;
  /** True once any fragment declared a producer, so "none" and "empty" differ. */
  let bufferSawProducer = false;
  /** True when two fragments of ONE buffer declared DIFFERENT producers. */
  let bufferProducerConflict = false;

  /** A producer tag as the worker writes it: a non-empty trimmed string, or null. */
  function producerOf(meta) {
    const value = meta && typeof meta.producer === 'string' ? meta.producer.trim() : '';
    return value || null;
  }

  /**
   * Remember the fragment's producer. Called from `ingest`, once per fragment.
   *
   * A conflict is STICKY and so is the refusal it produces: if the first fragment
   * says `redux` and a later one says `live`, the line is not "live" and it is not
   * "redux" — it is unprovable, and an unprovable canonical line is refused.
   */
  function rememberProducer(meta) {
    const value = producerOf(meta);
    if (value === null) return;
    bufferSawProducer = true;
    if (bufferProducer === null) {
      bufferProducer = value;
      return;
    }
    if (bufferProducer !== value) bufferProducerConflict = true;
  }

  /** The tag this commit may carry: the buffer's one agreed value, or NOTHING. */
  function committedProducer() {
    if (!bufferSawProducer || bufferProducerConflict) return null;
    return bufferProducer;
  }

  /**
   * The routes a commit can carry, and the ONE rule that decides between them.
   *
   *   'final'             — a worker-CLOSED line: the transcript (the HISTORY
   *                         feed) takes it. Either the worker said so itself
   *                         (`final:true`) or — when the worker stamps no route
   *                         at all, which is the pipeline as it stands — the
   *                         AUDIO closed the line (a real gap in speech, or the
   *                         length cap), NOT the panel's own deadline.
   *   'provisional-draft' — the LIVE caption: the box paints it, the transcript
   *                         may NEVER take it. This is the panel's own hold
   *                         deadline (`hold-timeout`) or a worker status change
   *                         (`status-change`/`flush`) — MEASURED as the defect:
   *                         10 of 10 lines the owner read as "the live caption"
   *                         carried `reason=status-change`.
   *
   * The worker's vote WINS when it is present (both `final:true` and
   * `final:false`), so once `worker/sotto_worker.py:_event` stamps the flag the
   * panel follows it exactly. See `_main/panel-live-vs-history-probe.js`.
   *
   * ── THE FALLBACK MUST BE ABLE TO SAY IT ENGAGED ─────────────────────────
   *
   * The last branch below returns `'final'` when the worker stamped NOTHING,
   * and that is DELIBERATE — it is NOT to be deleted. The live worker is the
   * pre-cure snapshot (`worker/sotto_worker.py`, 128569 B) whose `_event` never
   * stamps `final`; removing the wrap would blank the owner's transcript.
   *
   * But a fallback that cannot say it engaged is the same defect class as a
   * gate that cannot say no. MEASURED consequence: when the worker's M2 contract
   * (`line_events` / `take_closed` / `_event(final=)`) was de-landed, the
   * renderer kept emitting `route=final` from this very default and THE
   * DE-LANDING PASSED SILENTLY — the loss went unnoticed for a day (lane
   * SottoCaptionLines, `_main/receipt-20261007-caption-lines.md`, sha
   * `039f80b9…`; P1 ticket `4fb5b25380cbc8269977e22e`).
   *
   * `routeSourceFor()` below turns that case into a DIFFERENT observable: a
   * commit that reached the transcript ONLY because this else-half manufactured
   * it is stamped `routeSource:'fallback'`, never the same `'worker-stamped'` a
   * genuine worker vote produces.
   */
  const PANEL_DEADLINE_REASON = /^(hold-timeout|status-change|flush)/;

  function routeFor(reason) {
    if (bufferFinal) return 'final';
    if (bufferSawFinal) return 'provisional-draft';
    return PANEL_DEADLINE_REASON.test(String(reason == null ? '' : reason))
      ? 'provisional-draft'
      : 'final';
  }

  /**
   * WHICH branch produced the route — so the FALLBACK can SAY IT ENGAGED.
   *
   * The source is DERIVED from the route `routeFor` just returned plus the
   * worker-vote predicate, and is NEVER a re-listing of the branches, so the
   * two can never silently disagree: if `routeFor` ever changes which default
   * it manufactures, this still labels the outcome by how it was decided.
   *
   *   'worker-stamped' — a worker vote decided it (`final:true` -> 'final';
   *                      `final:false` -> 'provisional-draft'). ARM A of
   *                      `_main/silent-fallback-probe.js`.
   *   'panel-deadline' — no worker vote; the PANEL's own hold deadline or a
   *                      status flush decided it ('provisional-draft').
   *   'fallback'       — no worker vote AND the route is 'final': the line
   *                      reached the transcript ONLY because `routeFor`'s
   *                      else-half manufactured it. THIS IS THE DE-LANDING,
   *                      ANNOUNCED (P1 `4fb5b25380cbc8269977e22e`). ARM B.
   *
   * Read it from the SAME state `routeFor` reads, and only BEFORE `takeBuffer`
   * clears `bufferFinal`/`bufferSawFinal` (this is called from `commit`, right
   * after `routeFor`). It lands in the commit meta as `routeSource`, and the
   * stores write it on the line as `src=` so a transcript of `src=fallback` is
   * the de-landing, readable without running the panel.
   */
  function routeSourceFor(route) {
    if (bufferFinal || bufferSawFinal) return 'worker-stamped';
    // A line that DECLARES its producer answers the same question from a
    // different fact: which pass produced this text. It is named separately from
    // `'worker-stamped'` (which means "the worker's `final` flag decided the
    // route") so a transcript can still tell a route vote from a producer claim,
    // and so `'fallback'` keeps meaning exactly one thing: the silent default
    // engaged, with NO worker statement about this line at all (P1
    // `4fb5b25380cbc8269977e22e`). A producer-stamped line is not that case: the
    // worker DID speak about it.
    if (committedProducer() !== null) return 'worker-stamped-producer';
    return route === 'final' ? 'fallback' : 'panel-deadline';
  }

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
    // The route belongs to the BUFFER that is being drained, never to the
    // next one: a `final:true` line must not stamp the line that follows it.
    bufferFinal = false;
    bufferSawFinal = false;
    lineStart = null;
    // Same law for the producer tag: a `redux` batch line must not lend its tag
    // to the live line that follows it in the same buffer slot.
    bufferProducer = null;
    bufferSawProducer = false;
    bufferProducerConflict = false;
    return all;
  }

  /** Freeze what is on screen into one final, formulated line. */
  function commit(reason) {
    // Read the buffer's route BEFORE `takeBuffer` clears it (M5/M8): the meta
    // handed to the panel is what decides whether this line may enter the
    // transcript at all.
    const route = routeFor(reason);
    // Which branch produced that route — READ BEFORE `takeBuffer` clears the
    // worker-vote flags it reads. `'fallback'` is the silent default announcing
    // itself; see `routeSourceFor` and P1 `4fb5b25380cbc8269977e22e`.
    const routeSource = routeSourceFor(route);
    // The worker's producer tag, read under the same "before takeBuffer" rule:
    // it is the field `history-source.js` admits the canonical transcript on, and
    // it is forwarded ONLY when the whole buffer agreed on it (see
    // `committedProducer`) — never invented, never defaulted, never guessed.
    const tag = committedProducer();
    const start = lineStart;
    const all = takeBuffer();
    if (!all.length) return '';
    const line = formulate(all.map((t) => t.w).join(' '));
    if (line) {
      // The literal below is spelled out rather than left implicit, because the
      // ONE thing a reader must be able to check is that `producer` is present
      // only when the worker declared one: an absent key is the fail-closed
      // answer the store's guard depends on. (The OBJECT KEY is the worker's
      // field name; the local variable deliberately is not, so a grep for a
      // "producer" ASSIGNMENT finds only the places that really stamp one.)
      onCommit(line, reason, tag === null
        ? { route, start, routeSource }
        : { route, start, routeSource, producer: tag });
      // Remember what this line covers. `emittedWords` is NOT set here: it is
      // set by `ingest` from the fragment, because a continuation is stripped
      // and only the fragment knows the full line the worker is holding.
      emittedEnd = audioEndOf(all);
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

    if (!opening.length) return;

    // SPLIT (M5): the fragment's own route, from the worker's `final` flag.
    // `final:true` marks the line the worker CLOSED (its second pass over the
    // whole segment — the "redux" line the transcript carries) and is STICKY
    // for the buffer, so a partial that arrived before it cannot downgrade it.
    // An ABSENT flag is NOT trusted as closed: `bufferFinal` stays false, the
    // route stays `provisional-draft`, and the panel/store then refuse to put
    // the live caption in the history. Fail-closed on purpose — the old
    // permissive default is the defect this closes.
    if (meta && typeof meta.final === 'boolean') bufferSawFinal = true;
    if (meta && meta.final === true) bufferFinal = true;
    // The producer tag of this fragment, remembered for `commit` — the field the
    // canonical transcript's guard reads, and the one this engine used to drop.
    rememberProducer(meta);
    if (lineStart === null) lineStart = start;

    // The watermark is the worker's LINE as last seen: every partial of one
    // line is cumulative, so the next one is compared against this.
    emittedStart = start;
    emittedWords = fragWords;

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

  /**
   * DROP EVERYTHING THE ENGINE IS HOLDING — the Clear control.
   *
   * WHY THIS EXISTS. Clear used to empty the DOM only, and the engine kept its
   * buffer: `emittedStart`/`emittedWords`/`emittedEnd` survive `commit` on
   * purpose (they are the re-cover watermark that stops the worker's growth
   * partial from being written twice), so after a Clear the very next fragment
   * of the SAME worker line still matched the watermark, and the panel
   * re-rendered the words the owner had just cleared. Clearing the box has to
   * clear the STATE, not the paint.
   *
   * The ten fields below are every piece of state `createEngine` closes over
   * except the `reentered` guard, which is only ever true inside `ingest`'s own
   * recursion and is therefore always false whenever this can be called. The
   * routes are dropped with the words: a `final:true` line that was cleared must
   * not stamp the next line's route.
   *
   * API surface is otherwise unchanged — one method added, nothing removed.
   */
  function reset() {
    committed = [];
    provisional = [];
    prevWords = [];
    emittedEnd = null;
    emittedStart = null;
    emittedWords = [];
    lineStart = null;
    bufferFinal = false;
    bufferSawFinal = false;
    bufferProducer = null;
    bufferSawProducer = false;
    bufferProducerConflict = false;
    lastAudioEnd = null;
  }

  return {
    ingest,
    flush,
    expireHold,
    reset,
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
  formulate,
  healSeams,
  describeReadiness,
  agreedPrefixLength,
  words,
  SENTENCE_GAP_S,
  SENTENCE_MAX_CHARS,
  COMMIT_MAX_HOLD_MS,
  READY_SECONDS_MEASURED,
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
