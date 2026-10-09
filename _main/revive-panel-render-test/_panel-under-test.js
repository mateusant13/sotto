'use strict';

/**
 * Sotto — the panel renderer (v3: the live box is the product).
 *
 * TOP      header      the wordmark and the two controls (pause, hide), hide
 *                      LAST so it sits rightmost — the owner's 2026-10-08 ruling,
 *                      satisfied by document order in `panel.html` because this
 *                      module never re-parents them (lookups only: `:69` by id,
 *                      `:93`/`:1505`/`:1652` by `[data-pause-trigger]`).
 * THEN     `#history`  the canonical transcript: a feed read back from disk.
 *                      SECONDARY. With no canonical (batch) producer it stays
 *                      COLLAPSED to one bar (label, folder path, one honest
 *                      note, a chevron) and gives the height back to the live
 *                      box; it opens by itself the day `history.root()` reports
 *                      a producer. Its search is disabled while nothing can
 *                      write it — see `applyTranscriptMode`.
 * THEN     `#captions` the LIVE caption box: the streaming caption growing line
 *                      by line. THE PRODUCT, and the only flexible row in the
 *                      grid — it takes the panel's free height. It is BELOW the
 *                      transcript because the owner ruled so, verbatim
 *                      (2026-10-08): *"a legenda ao vivo, no painel, tem que
 *                      ficar embaixo do painel. o historico a cima"*. The DOM
 *                      order and `panel.css`'s `grid-template-rows` are ONE
 *                      decision: the `1fr` is assigned in document order.
 * BOTTOM   `.status`   the status line, up to two lines so the cause is not the
 *                      part that gets cut.
 *
 * The renderer owns the DOM and nothing else. Two things come from outside:
 *   * captions, through `window.sotto.onCaption` (the preload/WebView2 bridge);
 *   * the transcript store, through `window.sotto.history` (append/tail/search/
 *     reveal/root) — implemented by whichever shell is hosting the page.
 *
 * The history API is probed, never assumed: an older shell without it degrades
 * to a working live box and an explicit "transcript unavailable" note, instead
 * of a renderer that throws on load. Every element this file reaches for is
 * null-checked, for the same reason: `_main/_audit-render/panel-harness.html`
 * loads THIS file against an older copy of the markup.
 */

/** Cap on rendered LIVE lines, matching MAX_CAPTIONS in the shell. */
const MAX_CAPTIONS = 200;
/** Cap on history entries held in the feed (newest kept). */
const MAX_HISTORY = 500;
/** How many entries a fresh `tail()` loads. */
const HISTORY_LOAD = 400;
const dom = {
  panel: document.getElementById('panel'),
  // live caption box
  captions: document.getElementById('captions-body'),
  placeholder: document.getElementById('placeholder'),
  list: document.getElementById('caption-list'),
  captionsHint: document.getElementById('captions-hint'),
  statsChip: document.getElementById('stats-chip'),
  // transcript feed
  transcript: document.getElementById('history'),
  transcriptToggle: document.getElementById('history-toggle'),
  transcriptNote: document.getElementById('transcript-note'),
  transcriptCount: document.getElementById('history-count'),
  historyList: document.getElementById('history-list'),
  historyRoot: document.getElementById('history-root'),
  historyStatus: document.getElementById('history-status'),
  historyGallery: document.getElementById('history-gallery'),
  revealButton: document.getElementById('reveal-button'),
  searchForm: document.getElementById('search-form'),
  searchInput: document.getElementById('search-input'),
  searchButton: document.getElementById('search-button'),
  searchClear: document.getElementById('search-clear'),
  // footer
  status: document.getElementById('status'),
  statusText: document.getElementById('status-text'),
  statusDot: document.getElementById('status-dot'),
  hideButton: document.getElementById('hide-button'),
  // `quitButton` and `clearButton` were here and are gone with their controls (the
  // owner removed both from `panel.html`). The KEYS went too, not just the markup:
  // `dom.clearButton.addEventListener` was unguarded, so a markup-only removal threw
  // at wire time — and a `null` entry kept here would reproduce that throw for the
  // next reader. What the removals cost is recorded at both sites in `panel.html`
  // and in `_main/receipt-panel-stale-oracles.md` §11.
  // the strip surface's control row (`panel.html` `.stripbar`) — `null` on a
  // shell or an older harness that does not ship it, because every handler below
  // null-checks: `_main/_audit-render/panel-harness.html` loads THIS file against
  // markup that may be older than it.
  stripControls: document.getElementById('strip-controls'),
  stripLiveButton: document.getElementById('strip-live-button'),
  stripLiveLabel: document.getElementById('strip-live-label'),
  stripPauseButtons: document.querySelectorAll('[data-pause-trigger]'),
  stripState: document.getElementById('strip-state'),
  stripWord: document.getElementById('strip-word'),
  stripOpenButton: document.getElementById('strip-open-button'),
  // the pause confirmation (`panel.html`, outside `.panel` so the slab's own
  // `overflow: hidden` cannot clip its backdrop)
  pauseDialog: document.getElementById('pause-dialog'),
  pauseConfirmButton: document.getElementById('pause-confirm-button'),
  pauseCancelButton: document.getElementById('pause-cancel-button'),
  pauseShellNote: document.getElementById('pause-dialog-shell'),
  pauseButtons: document.querySelectorAll('[data-pause-trigger]'),
  panelPauseButton: document.getElementById('panel-pause-button'),
};

const bridge = window.sotto;
/** The history store, or null when the hosting shell does not implement it. */
const historyApi = bridge && bridge.history ? bridge.history : null;

/**
 * When the pipeline started, so readiness can state the MEASURED warm-up
 * instead of implying the owner is looking at a sequence of failures.
 */
const pipelineStartedAt = Date.now();

// ---------------------------------------------------------------------------
// MODULE STATE THAT THE INIT BLOCK BELOW REACHES — DECLARED FIRST, ON PURPOSE
// ---------------------------------------------------------------------------
// MEASURED 2026-10-07, on the owner's screen with a video playing: the worker
// transcribed for 20+ seconds at peak 0.44, the shell logged thousands of
// `BRIDGE_CAPTION_SENT delivered=true`, and the panel stayed frozen on
// "Starting the worker" with `#caption-list` at `display:none`. The cause was
// ONE `let` in the wrong place:
//
//     panel.js:87   wireHistory()          <- runs at module init
//     panel.js:304  markRevealState()
//     panel.js:428  reads `selectedEntry`  <- `let` declared at :263, BELOW
//
// `let`/`const` are hoisted but NOT initialised, so reading one above its
// declaration is a ReferenceError (the temporal dead zone). The throw aborted
// the init block at its first statement — so `wireCaptions()`, `wireStatus()`,
// `wireStats()` and `wireControls()` NEVER RAN, on every launch, and the panel
// looked merely quiet instead of broken. Nothing in the shell's log could see
// it (Python only sees its own `evaluate_js` call, which succeeded); it took
// the `window.addEventListener('error')` hook added to the injected bridge the
// same day. The lesson is the ordering rule this block now enforces: any state
// an init call can touch is DECLARED ABOVE the init block.
//
// Every entry held in the feed, oldest first.
let historyEntries = [];
/** The entry currently selected (its file is what "Show in folder" opens). */
let selectedEntry = null;
/**
 * STICKY FOLLOW for the live box: true while the owner is watching the newest
 * line. Declared HERE (above the init block) because `followNewestLine` reads it
 * from the caption path — see the temporal-dead-zone note above.
 *
 * MEASURED 2026-10-07, the owner's words: *"a transcrição não tá dando auto
 * scroll no painel"*. The old rule was "scroll only if the box is ALREADY within
 * 48 px of the bottom" (`scrollHeight - scrollTop - clientHeight < 48`), which is
 * a rule that can never START: with `scrollTop = 0` and a list already taller
 * than the 288 px box, that expression is hundreds of pixels, so the panel showed
 * the OLDEST lines forever while the newest accumulated below the fold — the
 * captions looked like they had stopped arriving. The rule that works is the
 * chat-style one: follow by default, stop the moment the owner scrolls away from
 * the bottom, resume the moment he comes back.
 */
let stickToNewest = true;
/** Non-empty while the feed is showing SEARCH RESULTS instead of the feed. */
let searchQuery = '';
/** The result set backing the current search view. */
let searchHits = [];
/**
 * THE GALLERY'S OWN STATE — which range is chosen, and which bucket is open.
 *
 * Declared HERE, above the init block, for the rule this file learned the hard
 * way (the `selectedEntry` temporal-dead-zone bug): anything the init block can
 * reach is declared above it.
 *
 * `galleryPick` is `null` on purpose and that null is the owner's request. He
 * asked for the drawer to stop filling itself (*"tira o historico que ja mostra
 * sozinho"*), so "no bucket chosen" is a REAL state that paints the buttons and
 * no lines — not a transient to be filled in by the first entry that arrives.
 */
let galleryRange = '24h';
let galleryPick = null;
/**
 * D1 — THE CANONICAL PRODUCER the shell reports from `history.root()`, or null.
 *
 * This is the ONE field that decides whether the transcript section is a live
 * feed or an honest closed drawer: `null` means nothing writes the canonical
 * transcript, so the section collapses, its search is disabled, and the note in
 * the bar says why. It is never invented here — absent/unknown is null, which is
 * the fail-closed reading.
 */
let canonicalProducer = null;
/**
 * THE TWO SURFACES (owner, 2026-10-08) — and every piece of state behind them,
 * declared HERE for the reason the note above gives: the init block below calls
 * `wireSurfaces()`, so a `let` written further down would be a temporal-dead-zone
 * ReferenceError that aborts the whole module and leaves the panel mute.
 *
 *   liveEnabled      the Live on/off toggle. `true` is what the app ships with:
 *                    the streaming engine runs while the panel is open, and the
 *                    toggle is how the owner turns it off without quitting. It is
 *                    the LOCAL belief until the shell confirms (`setLiveEnabled`),
 *                    and the button reports which of the two it is showing.
 *   paused           after a CONFIRMED pause. Nothing is transcribed until the
 *                    shell resumes, so the strip says so rather than looking idle.
 *   statusSnapshot   the last status the shell sent ({ text, kind }). The strip's
 *                    one-word status is read from it, so the word and the sentence
 *                    below can never disagree with each other.
 *   surfaceListeners set of callbacks told when the surface changes.
 *   pendingFocusReturn  the element focus came from before the dialog opened, so
 *                    Cancel gives it back. NEVER an autofocus: the panel does not
 *                    steal focus from the window underneath it.
 */
let liveEnabled = true;
let paused = false;
let pauseSupported = false;
let liveSupported = false;
let statusSnapshot = { text: '', kind: null };

// `transcriptExpanded` LIVES HERE, not beside `wireHistory` — see its own long
// comment below. It is read from `applyTranscriptMode`, which the init block
// reaches through `wireHistory` → `loadHistory`, and a `let` read before its own
// line is a ReferenceError that takes every later init call with it.
let transcriptExpanded = null;

// ── THE STATUS IS A REPAIR CONTROL, AND THESE TWO LIVE ABOVE THE INIT BLOCK ──
// Owner's ruling, verbatim (2026-10-08): *"e o botao de error ou de idle sei
// que, ao clicar, deve fazer a pipeline inteira ser revivida, se nao tiver
// funcionando"*. `wireRevive` below is that click. The hint is a CONSTANT and
// it is declared here, above the init block, because `updateStripState` reads
// it on every status — and anything the init block can reach is declared above
// it (the rule the 2026-10-07 TDZ bug bought, see AGENTS.md).
const REVIVE_HINT = 'click to restart the pipeline (reloads the live engine)';
const REVIVE_TITLE = 'Restart the pipeline — reloads the live engine';
//: True between asking the shell for a revive and giving up on an answer. The
//: SHELL also refuses a second respawn (`REVIVE_REFUSED`); this flag is what
//: lets the panel say so without a round trip it does not have.
let reviveInFlight = false;
let pendingFocusReturn = null;
/** The history root the shell reported, or null. */
let historyRootPath = null;
/**
 * LINE IDENTITY (owner, 2026-10-08, verbatim: *"essa repeticao de linhas tem que
 * acabar ... nao tem que repetir linha e com append na proxima"*).
 *
 * ONE live-box line per worker SEGMENT, and the segment's identity is its
 * `start`. The worker narrates one line as a run of partials that all carry the
 * SAME `start` with `end` growing, and closes it with ONE `final:true` event —
 * and that final event is a REVISION, not necessarily a superset (the owner's own
 * `_main/webview-run.log` carries a segment whose final text differs from the
 * last partial: `...and on the right` -> `problems and use this skill...`).
 *
 * So a commit whose `start` is ALREADY the identity of a committed line REPLACES
 * that line's text IN PLACE; only a commit with a NEW `start` appends a row. The
 * map is what makes that decidable: without it, the second commit of one segment
 * looked like a second line, which is the duplication the owner is looking at.
 *
 * FAIL-SAFE DIRECTION: a commit with no usable identity (`start` absent — an
 * older worker, or a non-audio one) appends, exactly as before. Replacing the
 * wrong row would lose a line; appending at worst shows the old behaviour.
 *
 * Declared in this block on purpose — `addCaption` is reachable from the engine
 * the init block below creates, and a `let` read above its declaration is a
 * temporal-dead-zone ReferenceError that takes the whole module down (see the
 * note at the top of this file).
 */
let committedByStart = new Map();

/**
 * HOW MANY LINES THIS DOCUMENT HAS CLOSED — a DIAGNOSTIC counter, kept on the row
 * as `data-index` and NO LONGER PAINTED.
 *
 * The `bcast` direction prints this ordinal beside each line
 * (`pad3(h.id)` in
 * `H:\aireplay\docs\design\sotto-app-design-directions\src\components\Panel.tsx`),
 * and it was on screen as `033 11:21:03`. THE OWNER HAD IT REMOVED, verbatim
 * (2026-10-08): *"tira esse numero de 033 11:21:03. no caso tira esse 033"* — the
 * time stays, the ordinal goes. He left the door open for the other half
 * ("if the 033 is useful for diagnosis, keep it in the internal state but never on
 * screen"), so the counter and the `data-index` attribute SURVIVE and only the
 * `<span class="caption__index">` that carried it into the paint is gone. A probe
 * can still read `li[data-index]`; a human sees `11:21:03`.
 *
 * A MONOTONIC COUNTER, NOT A DOM POSITION, and that is still the whole point: a
 * CSS counter (or "index among siblings") RENUMBERS as `MAX_CAPTIONS` trims the
 * oldest rows off the top, so line 137 would silently become line 1. A REVISION of
 * a row keeps the ordinal it was born with (`committedByStart` identifies the row).
 *
 * Declared in this block on purpose: `addCaption` is reachable from the engine
 * the init block below creates, and a `let` read above its declaration is a
 * temporal-dead-zone ReferenceError that takes the whole module down (see the
 * note at the top of this file).
 */
let lineOrdinal = 0;
/**
 * THE WORDS CURRENTLY PAINTED in the one forming line, so a repaint can be
 * INCREMENTAL. The live box is rewritten on every partial, and the per-word
 * contrast ramp (`mano`) and the forming fog (`cine`) both need one span per
 * word — but recreating those spans on every partial would restart every
 * transition and throw away the very thing that makes the ramp gradual. So the
 * spans are REUSED by index and only the words that actually changed are
 * written; the ramp is repainted only when the TOTAL moves.
 */
let paintedWords = { confirmed: [], provisional: [], total: 0 };

/**
 * `pad3` — the mockup's own width for the line ordinal.
 *
 * KEPT even though nothing paints the ordinal any more: it is the FORMAT the
 * mockup defines, and the number is still written to `data-index` for the DOM
 * probes. It is used below by `stampOrdinal`, which is the single place the
 * ordinal is written, so this cannot become a function nobody calls.
 */
function pad3(n) {
  const s = String(Math.max(0, Math.trunc(n)));
  return s.length >= 3 ? s : '000'.slice(s.length) + s;
}

/** THE ONE PLACE THE ORDINAL IS STAMPED — on the ROW, never in the paint. */
function stampOrdinal(line, ordinal) {
  if (!line || typeof line.dataset !== 'object' || !line.dataset) return;
  line.dataset.index = String(ordinal);
  line.dataset.indexPadded = pad3(ordinal);
}

/** The ramp's own numbers, once, so the JS and the CSS cannot disagree. */
const WORD_RAMP = { min: 0.45, span: 0.55 };

/**
 * The contrast a word carries by POSITION in the forming line: the newest word
 * is at full contrast and every older one settles back.
 *
 * The direction's words (`designs.ts`, `mano`): *"cada palavra recém-chegada
 * ganha contraste aos poucos"* — and the mockup's own formula is
 * `0.45 + 0.55 · (i+1)/len`. It is computed HERE, once per word per total
 * change, and handed to CSS as `--w-op`; the theme decides whether to use it.
 */
function wordRamp(i, n) {
  if (!n) return '1';
  const v = WORD_RAMP.min + WORD_RAMP.span * ((i + 1) / n);
  return String(Math.round(v * 1000) / 1000);
}

/**
 * Paint a word list into a span, REUSING the spans that are already there.
 *
 * `offset`/`total` place these words in the FORMING LINE as a whole (the
 * confirmed part and the still-rewriteable tail are two hosts, one line), so the
 * ramp is continuous across the seam instead of restarting in the tail.
 *
 * The DOM shape is the one `panel.js` has always produced — words separated by
 * single spaces, so `textContent` reads exactly as the old `join(' ')` did, and
 * `.caption__confirmed` / `.caption__provisional` keep their meaning.
 */
function paintWords(host, words, offset, total, totalChanged, typingIndex) {
  if (!host) return;
  const typing = typeof typingIndex === 'number' ? typingIndex : -1;
  for (let i = 0; i < words.length; i += 1) {
    let span = host.children[i];
    let fresh = false;
    if (!span) {
      span = document.createElement('span');
      span.className = 'caption__word';
      host.append(span, document.createTextNode(' '));
      fresh = true;
    }
    // THE WORD'S IDENTITY IS IN `dataset.w`, NOT IN ITS `textContent`, and that
    // changed with the typing reveal: a typing word's textContent is now the
    // concatenation of its character spans, so writing `textContent` to it would
    // DESTROY the spans it is made of. The two facts that decide the paint are
    // "is this the same word" and "should this word be typing", and both are
    // cheap reads.
    const isTyping = i === typing;
    const wasTyping = span.dataset.typing === '1';
    if (span.dataset.w !== words[i] || wasTyping !== isTyping) {
      span.dataset.w = words[i];
      paintChars(span, words[i], isTyping);
    }
    if (fresh || totalChanged) {
      span.style.setProperty('--w-i', String(offset + i));
      span.style.setProperty('--w-n', String(total));
      span.style.setProperty('--w-op', wordRamp(offset + i, total));
    }
  }
  while (host.children.length > words.length) {
    const last = host.lastElementChild;
    const space = last.nextSibling;
    host.removeChild(last);
    if (space) host.removeChild(space);
  }
}

/**
 * The typing reveal's DOM: ONE `<span class="caption__ch">` PER CHARACTER, with
 * `--c-i` (its index in the word) stamped through CSSOM — never a `style=`
 * attribute, because `panel.html`'s CSP is `style-src 'self'` and a markup style
 * attribute is refused by it (measured; see the cost receipt §10).
 *
 * EVERY OTHER WORD AND EVERY COMMITTED WORD IS A PLAIN TEXT NODE. `typing` is
 * true for at most one word in the document — the newest word of the forming
 * line — so the extra elements are bounded by the longest word, not by the
 * transcript.
 *
 * THE THREE CASES THAT MATTER, and the reason this is not a one-line
 * `textContent =`:
 *   * GROWTH (`"casa"` → `"casas"`): the word gets LONGER as the model firms it
 *     up, and that is the common case. Only the NEW characters are appended, so
 *     the letters already on screen keep their finished animation instead of
 *     retyping themselves — a word that blinked and retyped on every fragment
 *     would be worse than no reveal at all.
 *   * REWRITE (`"casa"` → `"caso"`): the same length, so the characters are
 *     updated IN PLACE. The reveal does not restart; the letter simply changes.
 *   * NO LONGER THE NEWEST WORD (or a committed line): the spans are collapsed
 *     back to one text node, which renders identically to what was there.
 */
function paintChars(span, word, typing) {
  if (!typing) {
    delete span.dataset.typing;
    // THE TEXT IS ALWAYS WRITTEN — and that is not defensive, it is the bug this
    // function had for one revision: the first version only collapsed spans that
    // were ALREADY built, so a brand-new word (no `dataset.typing`, no children)
    // was left EMPTY and the whole line rendered blank. The cheap identity check
    // below keeps the write off the common path without ever skipping it.
    const kids = span.childNodes;
    if (kids.length === 1 && kids[0].nodeType === 3 && kids[0].data === word) return;
    span.replaceChildren(document.createTextNode(word));
    return;
  }
  span.dataset.typing = '1';
  // ANY CHILD THAT IS NOT ALREADY A CHARACTER SPAN IS A STALE TEXT NODE FROM A
  // DIFFERENT WORD, and dropping it is load-bearing — this is the second bug this
  // function shipped with, and it was measured, not guessed: `paintWords` reuses
  // the word spans BY INDEX, so when the engine commits a prefix and the forming
  // tail shifts left, the span at index `i` is repainted with a word it never
  // held. The write that used to clear that was `span.textContent = word`, which
  // replaces ALL children; the character spans do not, so `"a"` (left in the span
  // from `"O rato roeu a …"`) + `"nove"` rendered as **`"anove"`** — caught by
  // ARM S of `_panel2-dom-probe.js`, not by me.
  for (const node of [...span.childNodes]) {
    if (node.nodeType !== 1 || node.className !== 'caption__ch') span.removeChild(node);
  }
  const chars = Array.from(word);
  while (span.children.length > chars.length) {
    span.removeChild(span.lastElementChild);
  }
  for (let i = 0; i < chars.length; i += 1) {
    let ch = span.children[i];
    if (!ch) {
      ch = document.createElement('span');
      ch.className = 'caption__ch';
      ch.style.setProperty('--c-i', String(i));
      span.append(ch);
    }
    if (ch.textContent !== chars[i]) ch.textContent = chars[i];
  }
}

/** No bridge means no captions can ever arrive; say so instead of looking idle. */
if (!bridge) {
  if (dom.status) dom.status.classList.add('status--error');
  document.body.dataset.state = 'error';
  if (dom.statusText) dom.statusText.textContent = 'Preload bridge missing — captions are impossible';
  if (dom.placeholder) {
    const noBridgeTitle = dom.placeholder.querySelector('.captions__placeholder-title');
    const noBridgeBody = dom.placeholder.querySelector('.captions__placeholder-body');
    if (noBridgeTitle) noBridgeTitle.textContent = 'Panel not wired';
    if (noBridgeBody) noBridgeBody.textContent =
      'window.sotto is undefined. The preload script did not run, so no caption can reach this panel.';
  }
  setHistoryNote('Transcript unavailable: no bridge');
} else {
  wireHistory();
  wireCaptions();
  wireStatus();
  // Silent no-op unless the hosting shell exposes `onStats` (see `wireStats`).
  wireStats();
  wireControls();
  // THE TWO SURFACES, in this order: the surface decides which layout the rest
  // of the wiring paints into, and `wireControls` above has already bound the
  // controls that exist on BOTH of them.
  wireSurfaces();
  wireStripControls();
  wirePause();
  // The status is a repair control: one click revives the whole pipeline.
  wireRevive();
  announceReady();
  wireLevel();
}

// ---------------------------------------------------------------------------
// THE AUDIO LEVEL — REAL DATA OR NOTHING (declared ABOVE the init block, which
// reaches it, per the rule the 2026-10-07 TDZ bug bought)
// ---------------------------------------------------------------------------
// THE WAVE THE DESIGN DREW WAS FAKE, AND IT IS DELETED. `.chrome__meter` ran a
// pure CSS keyframe loop that animated identically with speech, with silence and
// with a DEAD WORKER — measured in `docs/research/12-audio-level-contract.md`.
// A wave that lies is worse than no wave, which is what the owner forbade.
//
// WHAT THE REAL DATA IS, and what is still missing (that document's finding, not
// a guess): the worker's `peak` is the MAXIMUM OF THE RUN so far — it only rises,
// so three ticks in a row print the same number while the `rms` drifts — and it
// is published at about ONE POINT PER 10 s, where a wave needs ~10/s. Both are
// being fixed in the worker and in the shell by other lanes; the contract this
// code is built against is `stats.peak` = the level OF ONE WINDOW, plus
// `stats.blocks`.
//
// SO THE WAVE IS MOUNTED AND OFF. It consumes `onStats`/`getStats` when a shell
// has them, keeps an N=128 history (≈12.8 s at 10 Hz), smooths it with an
// INSTANT ATTACK and a ~200 ms release, and paints five compositor-only bars.
// With no data the bars sit at the floor, `body[data-level="none"]` says so, and
// the probe asserts that they do not move.
const LEVEL = {
  /** Ring buffer of window levels, newest at `(head - 1 + N) % N`. */
  hist: new Float32Array(128),
  head: 0,
  n: 0,
  /** The smoothed value the bars show. */
  level: 0,
  /** False until a REAL measurement arrives — never inferred from anything. */
  have: false,
  /** Local clock of the last measurement, so a stale feed can be detected. */
  at: null,
};
/** Instant attack, ~200 ms release: without the release the bars shake. */
const LEVEL_RELEASE_MS = 200;
const LEVEL_FLOOR = 0.14;
let lastLevelPaint = 0;

// ---------------------------------------------------------------------------
// Caption formulation. The TEXT decisions live in `caption-formulation.js`,
// which is DOM-free precisely so an oracle can run the real functions outside
// Electron; this block owns only the wiring and the rendering of what the
// engine decides.
// ---------------------------------------------------------------------------

const engine = window.SottoFormulation.createEngine({
  // `reason` and `meta` are the provenance the engine computes at the moment of
  // the write — WHICH rule closed the line and WHERE in the audio it began.
  // Both used to be dropped here (M7/M8).
  onCommit: (text, reason, meta) => {
    // THE PROVISIONAL ROW HAS TO GO WHEN THE LINE IT SHOWED IS WRITTEN, and the
    // panel is the only place that can do it: the engine is DOM-free.
    //
    // MEASURED 2026-10-08 by `_main/_panel2-dom-probe.js`: feeding a worker-shaped
    // stream (a `final:true` line, then the next line's growing partial) left ONE
    // `<li>` holding both the committed text and the provisional tail. The flow
    // was `renderProvisional` (creates the open row) → `commit` → `addCaption`
    // (retires it, appends the committed row) → and then, because the ENGINE's
    // tail is empty at that instant, no `onProvisional` followed — so the row
    // `addCaption` had just retired was never replaced, `addCaption`'s own append
    // was the only row left, and the next fragment rewrote that same row in place.
    // The box therefore NEVER painted a closed line as a closed line: it always
    // showed one open row whose confirmed span had grown. That is not what the
    // owner reads (`panel.js` has always claimed "the box replaces, one row per
    // closed line").
    //
    // Retiring HERE and letting the next `renderProvisional` create a fresh open
    // row is the same rule `addCaption` already applied, moved to the moment the
    // line actually became final. If the engine still holds a tail, `onProvisional`
    // fires immediately after this (the engine's OWN order) and re-creates it.
    retireProvisional();
    addCaption(text, reason, meta);
  },
  onProvisional: (committed, provisional) => renderProvisional(committed, provisional),
});

/**
 * Restarted on every caption, and RE-ARMED while the engine is still holding a
 * PROVISIONAL line: the deadline no longer writes anything to the transcript
 * (M6 — see `expireHold`), so a timer that fired on a live provisional line
 * must go back to waiting rather than let the line be abandoned.
 *
 * F6 — THE GUARD THAT COULD NOT BE TRUE. This read
 * `engine.state().provisionalRoute`, a field `state()` never returned (its
 * three keys are `committed`, `provisional`, `lastAudioEnd`), so the test was
 * always `undefined` → false and the timer was NEVER re-armed: the first hold
 * deadline disarmed the deadline for the rest of the run, and a line that
 * stalled after it was held until the next fragment or the next status change.
 * The real field is the provisional TAIL itself — a non-empty array is exactly
 * "the engine is still holding something".
 */
let holdTimer = null;
function armHoldTimer() {
  clearTimeout(holdTimer);
  holdTimer = setTimeout(() => {
    holdTimer = null;
    engine.expireHold();
    if (engine.state().provisional.length) armHoldTimer();
  }, window.SottoFormulation.COMMIT_MAX_HOLD_MS);
}

/**
 * The provisional line: one `<li>` whose text is REWRITTEN IN PLACE as the
 * hypothesis changes. It is never acknowledged as applied until it commits,
 * because a caption the model later contradicts is not a caption.
 * The line contains two spans inside .caption__text: .caption__confirmed and
 * .caption__provisional, so we can update the provisional part without
 * touching the confirmed part (which avoids flicker).
 *
 * ── WHAT CHANGED 2026-10-08, AND WHY IT IS STILL "REWRITTEN IN PLACE" ────────
 * Each WORD is now its own `<span class="caption__word">`, carrying `--w-i`,
 * `--w-n` and `--w-op` (see `paintWords`). Two directions need per-word handles
 * and neither could be built without them:
 *
 *   * `mano` — "cada palavra recém-chegada ganha contraste aos poucos". The ramp
 *     is `--w-op`, and the theme transitions `opacity` to it: an OPACITY
 *     transition, which the compositor owns, on a span that is REUSED (not
 *     recreated) so the transition is never restarted by the next partial.
 *   * `cine` — "a frase fechada é sólida; a em curso vive na névoa". The fog is
 *     a `filter: blur()` the theme applies to the tail span.
 *
 * AND THE THIRD HANDLE IS THE CHARACTER, added for the owner's first line in the
 * brief: *"TYPING letter-by-letter on the live line"*. The NEWEST WORD of the
 * forming line is split into one span per character by `paintChars`, and
 * `panel.css` reveals them one at a time with an `opacity` animation. That is
 * the only word in the document built this way, so the cost is bounded by the
 * longest word rather than by the transcript, and no committed text is affected.
 *
 * The contract is unchanged: ONE row per segment (identity = `start`), the
 * confirmed span is written only when its words changed, the tail span is the
 * one that moves, and nothing here animates a property that forces a relayout
 * (see `_main/receipt-panel-per-theme-chrome.md` §cost).
 */
function renderProvisional(committed, provisional) {
  if (!dom.list) return;
  const confWords = Array.isArray(committed) ? committed.map(t => t.w) : [];
  const provWords = Array.isArray(provisional) ? provisional.map(t => t.w) : [];
  const total = confWords.length + provWords.length;

  // Find or create the line that holds the provisional hypothesis.
  let line = dom.list.querySelector('.caption--provisional');
  if (!line) {
    line = document.createElement('li');
    line.className = 'caption caption--provisional';
    // The ordinal this line will be born with when it commits. STAMPED ON THE
    // ROW ONLY (`data-index` / `data-index-padded`) — the `<span>` that used to
    // paint it is gone, by the owner's own instruction (2026-10-08): *"to falando
    // desse numero a esquerda. o vermelho. nao é pra ter mais ele"*. A probe can
    // still read the ordinal; nobody sees it.
    stampOrdinal(line, lineOrdinal + 1);

    // The direction's own indicator (`inst`): a REAL element, because a
    // border-left cannot be animated on the compositor and the direction's one
    // dynamic element is exactly this LED. `display: none` for the other four
    // directions — see `panel.css`.
    const led = document.createElement('span');
    led.className = 'caption__led';
    led.setAttribute('aria-hidden', 'true');

    const time = document.createElement('span');
    time.className = 'caption__time';
    time.textContent = clockTime();

    const body = document.createElement('span');
    body.className = 'caption__text';

    // Inside the body we have two spans: one for confirmed, one for provisional.
    const confirmedSpan = document.createElement('span');
    confirmedSpan.className = 'caption__confirmed';
    const provisionalSpan = document.createElement('span');
    provisionalSpan.className = 'caption__provisional';
    // The tail marker ('·'), its own element so a theme can style it and so the
    // word spans above stay countable by `paintWords`.
    const mark = document.createElement('span');
    mark.className = 'caption__mark';

    body.append(confirmedSpan, provisionalSpan, mark);
    line.append(led, time, body);
    dom.list.append(line);
    paintedWords = { confirmed: [], provisional: [], total: 0 };
    followNewestLine();
  }

  // Update the two inner spans IN PLACE — reusing every span that already holds
  // the right word (see `paintWords`).
  const totalChanged = total !== paintedWords.total;
  paintWords(line.querySelector('.caption__confirmed'), confWords, 0, total, totalChanged);
  // AND THE TYPING REVEAL, on the newest word of the forming line — see
  // `paintChars`. `provWords.length - 1` is `-1` for an empty tail, which is
  // exactly "nothing types": a line whose words have all settled is text the
  // model has stopped reconsidering, and retyping it would be a lie about what
  // just arrived.
  paintWords(line.querySelector('.caption__provisional'), provWords,
    confWords.length, total, totalChanged, provWords.length - 1);
  const mark = line.querySelector('.caption__mark');
  if (mark) mark.textContent = provWords.length ? '▍' : '';
  paintedWords = { confirmed: confWords, provisional: provWords, total };
  // AND FOLLOW, because this is a GROWTH, not an append: the line gets taller
  // while the sentence is still being formed — the exact moment the owner is
  // watching. Following only on creation (above) left the newest words below the
  // fold for the whole interesting part of the line (measured 2026-10-07).
  followNewestLine();
  // ── AND THE FROZEN SKIN, IF THIS THEME HAS ONE (owner, 2026-10-08) ────────
  // The same two word arrays, painted into the MOCKUP'S OWN caption plate instead
  // of ours (`skin-host.js`). `panel.js` stays the single source of the text: the
  // skin is told what to show, it never reads the bridge itself, so a broken skin
  // cannot corrupt the caption and every existing DOM oracle keeps its own DOM.
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.live({ committed: confWords, provisional: provWords });
  }
}

/** Drop the provisional line: its words are now committed text. */
function retireProvisional() {
  if (!dom.list) return;
  const line = dom.list.querySelector('.caption--provisional');
  if (line) dom.list.removeChild(line);
  paintedWords = { confirmed: [], provisional: [], total: 0 };
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.live({ committed: [], provisional: [] });
  }
}

function wireCaptions() {
  // The follow is armed BEFORE the first caption can arrive: the scroll listener
  // is what keeps `stickToNewest` honest, and a panel that has never seen a
  // scroll event must still follow the newest line (that is the whole bug the
  // flag exists for).
  wireFollow();
  // `meta` carries the audio seconds. They are what let the engine tell a NEW
  // word from a RE-READ one, so they are not optional decoration.
  bridge.onCaption(({ text, meta }) => {
    // Any fragment at all means the stream is alive, so the previous deadline
    // is void before the engine decides anything.
    armHoldTimer();
    engine.ingest(String(text || '').trim(), meta || {});
  });
}

/**
 * A committed caption line: final text, acknowledged, and recorded in history.
 *
 * `reason` is the rule that closed the line and `meta` is the route + the audio
 * position the engine stamped on it (M7/M8). Both travel to the store, which
 * writes them on the line — the transcript used to be written with no way at all
 * to tell a closed sentence from a fragment.
 */
function addCaption(text, reason, meta) {
  if (!text) return false;
  if (!dom.list) return false;

  retireProvisional();
  if (dom.placeholder) dom.placeholder.hidden = true;
  dom.list.hidden = false;

  // WHICH LINE THIS IS. `meta.start` is the worker's own segment identity: every
  // partial of one segment carries the same `start` (see `committedByStart`).
  const start = meta && typeof meta.start === 'number' ? meta.start : null;
  const existing = start === null ? null : committedByStart.get(start) || null;
  if (existing && !existing.isConnected) committedByStart.delete(start);
  const line = existing && existing.isConnected ? existing : document.createElement('li');

  if (typeof line.dataset === 'object' && line.dataset) {    line.dataset.start = start === null ? '' : String(start);
    // Read by `_main/_panel2-repeat-probe.js` and by the DOM probes: the identity
    // is an attribute of the row, so what a probe asserts is what a human sees.
    line.dataset.revision = existing ? 'true' : 'false';
  }

  if (existing) {
    // REPLACE IN PLACE — the owner's rule. The row keeps its position and its
    // timestamp (it is the same moment of audio), and only its text moves; the
    // corrected words are never shown next to the ones they correct. It also
    // keeps its ORDINAL: a revision is the same line said better, not a new one.
    const body = existing.querySelector('.caption__text');
    if (body) body.textContent = text;
  } else {
    line.className = 'caption';
    // THE ORDINAL: a monotonic counter, so trimming `MAX_CAPTIONS` cannot
    // renumber what was said (see `lineOrdinal`). It is stamped on the ROW and
    // NOT PAINTED — the `bcast` direction's own index column was removed from the
    // screen at the owner's request (2026-10-08), twice, and it was the SAME
    // element on every row: *"nao é pra ter mais ele"*.
    lineOrdinal += 1;
    stampOrdinal(line, lineOrdinal);
    const time = document.createElement('span');
    time.className = 'caption__time';
    time.textContent = clockTime();
    const body = document.createElement('span');
    body.className = 'caption__text';
    body.textContent = text;
    line.append(time, body);
    dom.list.append(line);
    if (start !== null) committedByStart.set(start, line);
  }

  // Mark the newest line, drop the highlight from the previous one. A REVISED row
  // is the newest thing that happened, so the highlight follows the revision.
  const previous = dom.list.querySelector('.caption--latest');
  if (previous) previous.classList.remove('caption--latest');
  line.classList.add('caption--latest');

  while (dom.list.childElementCount > MAX_CAPTIONS) {
    const first = dom.list.firstElementChild;
    // The trimmed row leaves the index with it, or the map would hand a later
    // commit a node that is no longer in the box.
    const key = first && first.dataset ? first.dataset.start : '';
    if (key) committedByStart.delete(Number(key));
    dom.list.removeChild(first);
  }

  followNewestLine();
  updateLiveHint();
  recordHistory(text, reason, meta);
  bridge.captionApplied(text);
  setStatus('Receiving captions', 'live');
  // The frozen skin's own history list gets the same closed line (see `skin-host.js`).
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.line({ text, time: clockTime() });
  }
  return true;
}

/**
 * Follow the newest line — but only while the owner is watching the newest line,
 * and NEVER yank the view away from someone reading back.
 *
 * The flag is the fix (see `stickToNewest` above): "already near the bottom" can
 * never become true on its own. Programmatic scrolls also fire `scroll`, and they
 * land AT the bottom, so they keep the flag armed — which is what we want.
 */
function followNewestLine() {
  if (!stickToNewest) return;
  if (!dom.captions) return;
  dom.captions.scrollTop = dom.captions.scrollHeight;
}

/**
 * The owner's scroll is the ONLY thing allowed to stop the follow, and coming
 * back to the bottom is the only thing allowed to restart it. `passive: true`
 * because this listener never cancels the scroll and must not delay it.
 */
function wireFollow() {
  if (!dom.captions) return;
  dom.captions.addEventListener('scroll', () => {
    const { scrollTop, scrollHeight, clientHeight } = dom.captions;
    stickToNewest = (scrollHeight - scrollTop - clientHeight) < 48;
  }, { passive: true });
}

/**
 * THE LIVE BOX'S ROW COUNT IS NOT PAINTED EITHER. It read `6 lines` / `400 lines`
 * in the bar above the captions — the second of the two counts the owner pointed
 * at (*"…400 lines… 400 lines…"*). The count is still computed here and still
 * available to a probe through the DOM (`#caption-list` children), it is simply
 * not written to the screen: the bar keeps the label and the "behind" chip, which
 * says something the owner can ACT on, and drops the tally.
 */
function updateLiveHint() {
  if (!dom.list) return;
  void dom.list.childElementCount;
  if (dom.captionsHint) dom.captionsHint.textContent = '';
}

// ---------------------------------------------------------------------------
// History — the top feed, its disk store, the search and the "show in folder".
// ---------------------------------------------------------------------------
// NOTE: this section's state (`historyEntries`, `selectedEntry`, `searchQuery`,
// `searchHits`, `canonicalProducer`) is declared ABOVE, before the init block
// that calls `wireHistory()` — see the temporal-dead-zone note there. Do not
// re-add declarations here: a second `let` of the same name in one scope is a
// SyntaxError that takes the whole panel down.
/**
 * The owner's explicit drawer choice: null = follow the producer (the default),
 * true/false = the owner clicked the chevron and that choice stands.
 *
 * DECLARED ABOVE THE INIT BLOCK, AND IT WAS NOT — MOVED HERE 2026-10-08. It used
 * to sit 370 lines BELOW, next to `wireHistory`, and that is a temporal dead
 * zone waiting for a fast path: `wireHistory` (init) → `loadHistory` →
 * `renderFeed` → `applyTranscriptMode` → `isTranscriptExpanded`, which READS
 * this binding. With the shell's own bridge the tail arrives asynchronously and
 * the read lands after the module has finished evaluating — the panel works, and
 * the trap is invisible. The moment anything makes that path SYNCHRONOUS (a
 * shell with no `bridge.history`, which is the honest "no transcript writer yet"
 * case the panel itself handles) the init block dies with
 * `Cannot access 'transcriptExpanded' before initialization` and NOTHING after
 * it runs — no `wireStatus`, no caption subscription, a panel frozen on its
 * placeholder. Measured, in this file: `_main/revive-pipeline-oracle.py`
 * ARM P reproduced it on the first run against the REAL document.
 * `preload.js`'s fake bridge lacked `history` and that was enough to flip it.
 * Anything the init block can reach is declared above it — AGENTS.md, the rule
 * the 2026-10-07 TDZ bug bought.
 *
 * THE DECLARATION ITSELF LIVES ABOVE THE INIT BLOCK NOW; this comment stays here
 * because this is where a reader looks for the drawer's state. Do not re-add a
 * `let` on this line: a second declaration of the same name in one scope is a
 * SyntaxError, which takes the whole panel down harder than the TDZ did.
 */

function wireHistory() {
  // The drawer handle. It always works — that is the point of collapsing rather
  // than hiding: the owner can still read the folder and any rows that exist.
  if (dom.transcriptToggle) {
    dom.transcriptToggle.addEventListener('click', () => {
      transcriptExpanded = !isTranscriptExpanded();
      applyTranscriptMode();
      if (isTranscriptExpanded() && dom.historyList) {
        dom.historyList.scrollTop = dom.historyList.scrollHeight;
      }
    });
  }

  if (dom.revealButton) {
    dom.revealButton.addEventListener('click', () => {
      // Disabled until a line is selected, so this is a belt-and-braces guard and
      // not the only thing standing between the owner and a stray explorer window.
      if (!selectedEntry) return;
      revealPath(selectedEntry.path);
    });
  }
  if (dom.historyRoot) dom.historyRoot.addEventListener('click', () => revealPath(null));
  markRevealState();

  if (dom.searchForm) {
    dom.searchForm.addEventListener('submit', (event) => {
      event.preventDefault();
      runSearch(dom.searchInput ? dom.searchInput.value : '');
    });
  }
  if (dom.searchClear) {
    dom.searchClear.addEventListener('click', () => {
      if (dom.searchInput) dom.searchInput.value = '';
      runSearch('');
    });
  }

  // THE GALLERY — ONE delegated listener, because the buttons are rebuilt on every
  // render and per-button listeners would leak with them. A press reads the spec
  // off the button's own `dataset`, which is the same data the render wrote, so
  // there is no second table of what each button means.
  if (dom.historyGallery) {
    dom.historyGallery.addEventListener('click', (event) => {
      const btn = event.target && event.target.closest
        ? event.target.closest('.gallery__btn')
        : null;
      if (!btn) return;
      pickGallery({
        range: btn.dataset.range || '',
        day: btn.dataset.day || '',
        hour: btn.dataset.hour == null ? '' : btn.dataset.hour,
      });
    });
  }

  if (!historyApi) {
    setHistoryNote(
      'Transcript unavailable: this shell has no store (nothing is written)',
    );
    if (dom.revealButton) dom.revealButton.disabled = true;
    loadHistoryFromMemory();
    return;
  }

  historyApi
    .root()
    .then((r) => {
      const root = (r && r.root) || (typeof r === 'string' ? r : '');
      if (root) {
        // THE FOLDER PATH IS NOT PAINTED. The owner quoted it as one of the
        // strings to take off the screen (*"'h sotto history 400 lines…'"*), and
        // it was the widest thing in the bar. The button KEEPS its capability —
        // it still opens the folder, and the path is still in its `title`, so a
        // hover names the place and a click goes there — but the bar itself shows
        // a folder affordance instead of a path. The path is also still in the
        // internal state (`historyRootPath`), which is what the probe reads.
        historyRootPath = root;
        if (dom.historyRoot) {
          dom.historyRoot.textContent = '';
          dom.historyRoot.title = `Open ${root}`;
        }
      }
      // D1 — WHO writes this feed, as the shell reports it. `null` (today) means
      // the section must collapse and say so. Read AFTER the tail so the note
      // carries both the writer and the row count; `applyTranscriptMode` runs
      // again from `renderFeed` for that reason.
      canonicalProducer = canonicalProducerOf(r);
      applyTranscriptMode();
    })
    .catch(() => {});

  loadHistory();
}

/** `{canonicalProducer}`, or a bare string, or nothing at all — never invented. */
function canonicalProducerOf(result) {
  if (typeof result === 'string') return result.trim() || null;
  const value = result && result.canonicalProducer;
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/**
 * D1 — the transcript section's ONE state function.
 *
 * Collapsed unless the shell reports a canonical producer (or the owner opened
 * it by hand). While collapsed it is a bar: label, folder path, row count, the
 * honest one-line note, and the chevron. The LIVE search is disabled rather than
 * left as a box that can never match, and it re-enables itself the moment a
 * producer exists — nothing here is a permanent decision.
 */
function applyTranscriptMode() {
  const expanded = isTranscriptExpanded();
  const rows = historyEntries.length;

  if (dom.transcript) dom.transcript.classList.toggle('history--collapsed', !expanded);
  if (dom.transcriptToggle) {
    dom.transcriptToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    dom.transcriptToggle.title = expanded ? 'Collapse the transcript' : 'Expand the transcript';
  }
  if (dom.transcriptCount) {
    // THE THIRD COUNT SITE — the owner's own words suggested there was more than
    // one (*"400 lines… 400 lines…"*) and there were three: this one, the live
    // bar's tally and the note's prefix. All three stop painting. The element
    // stays in the DOM, hidden and empty, and `rows` is still the live state
    // (`historyEntries.length`), so nothing about the feed became unreadable to a
    // probe — only to the eye.
    dom.transcriptCount.textContent = '';
    dom.transcriptCount.hidden = true;
    void rows;
  }
  if (dom.transcriptNote) {
    const note = transcriptNoteText(rows);
    dom.transcriptNote.textContent = note;
    dom.transcriptNote.title = transcriptNoteTitle();
    // An empty note is HIDDEN, not left as a gap: the paragraph used to hold the
    // bar open for a sentence that is no longer painted.
    dom.transcriptNote.hidden = note === '';
  }

  const searchable = Boolean(canonicalProducer);
  if (dom.searchInput) {
    dom.searchInput.disabled = !searchable;
    dom.searchInput.placeholder = searchable ? 'Search transcript…' : 'No transcript writer yet';
    dom.searchInput.title = searchable
      ? `Search the canonical transcript (written by ${canonicalProducer})`
      : 'Search is off: nothing writes the transcript yet, so a search here can never match';
  }
  if (dom.searchButton) {
    // Deliberately NOT disabled: a disabled control explains nothing, and this
    // one carries the reason in its title and, on a click, in the note.
    dom.searchButton.title = searchable
      ? 'Search the transcript'
      : 'Search is off — no writer produces the transcript yet';
  }
  if (dom.searchClear && !searchable) dom.searchClear.hidden = true;

}

/** Auto = open only when something can write the feed. */
function isTranscriptExpanded() {
  if (transcriptExpanded !== null) return transcriptExpanded;
  return Boolean(canonicalProducer);
}

/**
 * THE COLLAPSED BAR CARRIES NO SENTENCE ANY MORE — the owner ruled, verbatim
 * (2026-10-08): *"tambem tira essas coisas como 'h sotto history 400 lines no
 * canonial writer 400 lines the transcript'"*. That is this line, the folder path
 * beside it and the row count above it: DIAGNOSTIC PROSE, painted where a product
 * sentence belongs. He had already had `Receiving captions` removed for the same
 * reason — the panel was telling him how it was built instead of what it heard.
 *
 * So the function is kept, still called, and still the ONE decision point, but it
 * now returns the empty string: the information is NOT lost, it moved to the
 * bar's `title` (a hover, i.e. something the owner asks for) and to the internal
 * state (`canonicalProducer`, `historyEntries.length`), which is exactly the
 * trade he offered: *"if it is useful for diagnosis, keep it in the internal
 * state but never on screen."* Nothing here invents a writer it does not have —
 * `transcriptNoteTitle` still refuses to claim one.
 */
function transcriptNoteText(rows) {
  void rows;
  return '';
}

/** The same sentence, unabbreviated, for the bar's tooltip. */
function transcriptNoteTitle() {
  return canonicalProducer
    ? `The canonical transcript is written by ${canonicalProducer}.`
    : 'Nothing writes the canonical transcript yet: the batch pass (Parakeet Redux) '
      + 'does not exist on this box, so the live engine\'s lines are refused here by design.';
}

/**
 * D5 — the "Show in folder" button is honest about what it can do: it opens the
 * SELECTED line, so with no selection it is disabled and says what to do first.
 * The folder path button next to it needs no selection and is always live.
 */
function markRevealState() {
  if (!dom.revealButton) return;
  const has = Boolean(selectedEntry);
  dom.revealButton.disabled = !has || !historyApi;
  dom.revealButton.title = has && selectedEntry.path
    ? `Show ${selectedEntry.path} in the OS file manager`
    : has
      ? 'Show the transcript folder in the OS file manager'
      : 'Select a transcript line first — this button opens the selected line';
}

/** Ask the shell for the newest entries and paint the feed. */
function loadHistory() {
  if (!historyApi || !historyApi.tail) return;
  historyApi
    .tail(HISTORY_LOAD)
    .then((r) => {
      const entries = normaliseEntries(r);
      historyEntries = entries;
      renderFeed();
    })
    .catch((err) => setHistoryNote('Transcript read failed: ' + errorText(err)));
}

/** A shell that has no history store still shows the captions it saw this run. */
function loadHistoryFromMemory() {
  renderFeed();
}

/**
 * Record a committed caption. The shell is the source of truth for the file
 * path (it names the folder), so the entry it returns is what the feed stores;
 * if the store is absent or fails, the caption still appears in the feed with
 * no path, and the failure is stated rather than hidden.
 */
function recordHistory(text, reason, meta) {
  // M8 — the line's provenance, as the store writes it on disk:
  //   route   which road closed this line: `final` (the worker's second pass
  //           over the whole segment, M3) or `provisional-draft` (a terminal
  //           flush of a line the worker never closed).
  //   start   the worker's LINE identity in audio seconds — the worker's own
  //           `start` field (`sotto_worker.py:_event`), not a panel invention.
  //   reason  the rule that fired at the moment of the write, which the panel
  //           already received and dropped.
  //
  // OWNER 2026-10-06, verbatim: "o historico simplesmente mostra a legenda ao
  // vivo, inves de mostrar a versao processada pelo redux."
  //
  // The transcript carries ONLY a line the WORKER closed (`route=final`: the
  // second pass over the whole segment, M3). A `provisional-draft` IS the live
  // caption — the box may show it, the history may not — and it used to reach
  // the file through `flush('status-change')` (see `wireStatus` below), which
  // fires on every worker status while this worker restarts constantly.
  // MEASURED in the owner's own `history/2026-10-06/10.md`: 9 of the 13 lines
  // written after the 2026-10-06 cure are
  // `route=provisional-draft reason=status-change`, word for word the live box
  // ("Em", "Antes dos", "Simplesmente", ...). See docs/audit/historico-vs-redux.md.
  // FAIL-CLOSED (owner 2026-10-06). The engine stamps every commit with the
  // route it derived from the worker's `final` flag (caption-formulation.js
  // `commit`): 'final' = the line the WORKER closed (its second pass — the
  // "redux" line the transcript carries), 'provisional-draft' = the LIVE
  // caption, which the box paints and the transcript may NEVER take.
  //
  // An ABSENT route is NOT a final line. The old `(meta && meta.route) ||
  // 'final'` default made this guard VACUOUS — MEASURED 2026-10-06: every
  // commit arrived with `route=null` and every one was written, so the WHOLE
  // live caption reached the transcript (the defect the owner reported).
  const route = meta && meta.route;
  if (route !== 'final') return;
  // OWNER 2026-10-07 — the SECOND half, and the one the owner reported missing:
  // the canonical transcript ("History · Redux") is a DIFFERENT SOURCE. A
  // `route=final` line the LIVE nvidia streaming engine produced is STILL the
  // live path's own history — verbatim the thing he forbids ("o historico nao e'
  // pra ser NUNCA o historico do live nvidia. e' pra ser do parakeet redux").
  // The transcript is reserved for the BATCH pass (`README.md:20`, Parakeet
  // Redux via `transcribe.cpp`), so a line must DECLARE that producer to enter
  // here. The live engine declares none, so `addCaption` -> `recordHistory` can
  // no longer feed HISTORY: the two fields no longer share a source. Fail-closed
  // — an absent or unknown producer is refused, never assumed canonical. The
  // decision lives in the DOM-free `history-source.js` so the oracle executes
  // THIS function; see `_main/live-vs-history-source-oracle.js`.
  const isCanonical = window.SottoHistorySource
    && window.SottoHistorySource.isCanonicalLine;
  if (!isCanonical || !isCanonical(meta)) return;
  // WHICH branch produced that `route` — the FALLBACK must ANNOUNCE itself
  // (P1 `4fb5b25380cbc8269977e22e`). `'worker-stamped'` = a worker vote decided
  // it (the worker's `final` flag); `'fallback'` = NO worker stamp was seen and
  // `caption-formulation.js routeFor`'s else-half MANUFACTURED this `final`.
  // The store writes it on the line as `src=`, so a transcript of `src=fallback`
  // is the de-landing, readable without running the panel. Absent meta keeps it
  // null: the field is never invented here.
  const routeSource = meta && typeof meta.routeSource === 'string' ? meta.routeSource : null;
  const options = {
    // Only a canonical (batch) line reaches here, so the source it declares is
    // the canonical producer — never `'live'` (that was the live path stamping
    // its own lines as the transcript). See the guard above.
    source: 'redux',
    route,
    routeSource,
    start: meta && typeof meta.start === 'number' ? meta.start : null,
    reason: reason || '',
  };
  // M8 — what the FILE gets. Usually the same string the box shows; for a line
  // the worker never closed the engine hands a `fileText` without the terminal
  // mark it would otherwise have INVENTED, so the transcript cannot dress a
  // fragment as a closed sentence.
  const body = meta && typeof meta.fileText === 'string' && meta.fileText
    ? meta.fileText
    : text;
  if (!historyApi || !historyApi.append) {
    pushEntry({ time: clockTime(), text: body, path: null });
    return;
  }
  historyApi
    .append(body, options)
    .then((r) => {
      const entry = (r && r.entry) || null;
      pushEntry(entry || { time: clockTime(), text, path: null });
    })
    .catch((err) => {
      setHistoryNote('History write failed: ' + errorText(err));
      pushEntry({ time: clockTime(), text, path: null });
    });
}

function pushEntry(entry) {
  historyEntries.push(entry);
  while (historyEntries.length > MAX_HISTORY) historyEntries.shift();

  if (searchQuery) {
    if (matches(entry.text, searchQuery)) {
      searchHits = [entry].concat(searchHits);
      renderSearchResults(searchQuery, searchHits);
    }
    return;
  }
  // A NEW LINE IS NOT PAINTED JUST BECAUSE IT EXISTS. With a bucket open, a line
  // that falls INSIDE it is appended, so the reader keeps his place and the list
  // still follows the newest; a line outside it, or no open bucket at all, leaves
  // the list alone — an unconditional append here would resurrect exactly the wall
  // of lines the owner had removed (*"tira o historico que ja mostra sozinho"*).
  const api = galleryApi();
  if (api && galleryPick && api.pick([entry], galleryPick.day, galleryPick.hour).length) {
    appendFeedRow(entry);
    return;
  }
  // The list's CONTENT is unchanged in that case (still the hint), so only the
  // gallery's buttons and counters need to move — including the new bucket itself,
  // which must appear even though its lines stay off screen until he asks.
  renderGallery();
}

/** The DOM-free gallery module, or null in a shell that does not ship it. */
function galleryApi() {
  return window.SottoHistoryGallery || null;
}

/** One gallery button. `spec` is what it selects; `on` marks the current pick. */
function galleryButton(label, spec, on, extraClass) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'gallery__btn' + (on ? ' is-active' : '') + (extraClass ? ' ' + extraClass : '');
  btn.textContent = label;
  btn.dataset.day = spec.day || '';
  btn.dataset.hour = spec.hour == null ? '' : spec.hour;
  btn.dataset.range = spec.range || '';
  if (spec.title) btn.title = spec.title;
  btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  return btn;
}

/**
 * THE GALLERY — the days and hours inside the chosen range, as BUTTONS.
 *
 * It is built from `historyEntries`, which the panel has ALREADY loaded: the
 * gallery costs no extra read of the store, and the shell needs no new method.
 * That is deliberate — the owner asked for navigation, not for a second reader.
 *
 * The RANGE decides which buckets exist (`24 h` first, then `1 h`, his order) and
 * the buckets are then grouped by day and hour by `history-gallery.js`. A range
 * with no entries paints NOTHING and hides itself, rather than offering buttons
 * that open an empty hour: a control that cannot do anything is worse than an
 * absent one.
 */
function renderGallery() {
  const host = dom.historyGallery;
  if (!host) return;
  const api = galleryApi();
  host.replaceChildren();
  if (!api) {
    host.hidden = true;
    return;
  }
  const now = new Date();
  const inRange = api.select(historyEntries, galleryRange, now);
  const grouped = api.buckets(inRange);
  // THE STORE IS EMPTY, so there is nothing to navigate and the gallery is gone.
  if (!historyEntries.length) {
    host.hidden = true;
    return;
  }
  host.hidden = false;

  // THE RANGE ROW IS PAINTED EVEN WHEN THE RANGE IS EMPTY — found by reading, not
  // by a failing arm: hiding the whole host when `grouped.days` was empty also hid
  // the `24 h` button, so picking `1 h` in a quiet hour left the owner with no way
  // back and no control on screen at all. The row is the way OUT of an empty range,
  // so it is painted first and unconditionally once the store holds anything.
  const ranges = document.createElement('div');
  ranges.className = 'gallery__row gallery__row--ranges';
  for (const r of api.RANGES) {
    ranges.append(galleryButton(r.label, { range: r.id }, galleryRange === r.id, 'gallery__range'));
  }
  host.append(ranges);

  if (!grouped.days.length) {
    // Honest, and specific about WHICH window is empty: "no entries" and "none in
    // the last hour" are different facts and only one of them is about the store.
    const spec = api.rangeOf(galleryRange);
    const warn = document.createElement('p');
    warn.className = 'gallery__warn';
    warn.textContent = spec
      ? `Nothing in the last ${spec.hours} h.`
      : 'That range is not one this panel offers.';
    host.append(warn);
    return;
  }

  for (const day of grouped.days) {
    const row = document.createElement('div');
    row.className = 'gallery__row';
    const dayOn = Boolean(galleryPick) && galleryPick.day === day.day && !galleryPick.hour;
    row.append(galleryButton(
      `${day.day} · ${day.count}`,
      { day: day.day, title: `All ${day.count} line(s) of ${day.day}` },
      dayOn,
      'gallery__day',
    ));
    for (const hour of day.hours) {
      const on = Boolean(galleryPick)
        && galleryPick.day === day.day && galleryPick.hour === hour.hour;
      row.append(galleryButton(
        hour.hour,
        {
          day: day.day,
          hour: hour.hour,
          title: `${hour.count} line(s) at ${hour.hour}h on ${day.day}`,
        },
        on,
        'gallery__hour',
      ));
    }
    host.append(row);
  }
  // An unreadable line is COUNTED here rather than dropped in silence: it is a
  // fact about the store, and a gallery that hid it would flatter the store.
  //
  // THE COUNT COMES FROM THE WHOLE STORE, NOT FROM `grouped`, and that is a defect
  // this arm found by going RED: `api.select` already refuses an entry it cannot
  // date (no stamp ⇒ `inRange` is false), so an undated line can NEVER reach
  // `buckets(inRange)` and `grouped.skipped` was therefore ALWAYS 0 — a warning
  // wired to a value that could not occur. Counting over `historyEntries` is what
  // makes it reachable, and the sentence no longer says "in this range", because
  // that is not where it was counted.
  const undated = api.buckets(historyEntries).skipped;
  if (undated) {
    const warn = document.createElement('p');
    warn.className = 'gallery__warn';
    warn.textContent = `${undated} line(s) of the transcript have no readable date and are not shown.`;
    host.append(warn);
  }
}

/** Apply a gallery press: a range clears the pick, a bucket opens it. */
function pickGallery(spec) {
  // A gallery press and a search are two views of the ONE list, so pressing a
  // button leaves search: otherwise the pick would paint its rows and the next
  // search result would silently overwrite them, and the owner would have no way
  // to tell which of the two he is looking at.
  if (searchQuery) {
    searchQuery = '';
    searchHits = [];
    if (dom.searchClear) dom.searchClear.hidden = true;
    setHistoryNote('');
  }
  if (spec.range) {
    galleryRange = spec.range;
    galleryPick = null;
  } else if (spec.day) {
    galleryPick = spec.hour ? { day: spec.day, hour: spec.hour } : { day: spec.day };
  }
  renderFeed();
}

function renderFeed() {
  if (!dom.historyList) return;
  clearList();
  renderGallery();
  const api = galleryApi();
  // THE OWNER'S REQUEST, as a branch: with no bucket chosen the list stays EMPTY
  // and says how to fill it. It does NOT fall back to painting every entry — that
  // fallback is the behaviour he had removed ("tira o historico que ja mostra
  // sozinho").
  const rows = api && galleryPick
    ? api.pick(historyEntries, galleryPick.day, galleryPick.hour)
    : null;
  if (!historyEntries.length) {
    const empty = document.createElement('li');
    empty.className = 'history__empty';
    empty.textContent = historyApi
      ? 'No transcript yet. Only the canonical batch pass writes here; the live '
        + 'engine never does.'
      : 'No transcript store in this shell.';
    dom.historyList.append(empty);
  } else if (rows) {
    if (!rows.length) {
      const empty = document.createElement('li');
      empty.className = 'history__empty';
      empty.textContent = 'That hour is empty.';
      dom.historyList.append(empty);
    } else {
      for (const entry of rows) dom.historyList.append(makeRow(entry));
      dom.historyList.scrollTop = 0;
    }
  } else {
    const hint = document.createElement('li');
    hint.className = 'history__empty history__empty--hint';
    hint.textContent = 'Pick a day or an hour above.';
    dom.historyList.append(hint);
  }
  // The bar's note and count are DERIVED from what the feed holds, so they are
  // refreshed wherever the feed is.
  applyTranscriptMode();
}

function appendFeedRow(entry) {
  if (!dom.historyList) return;
  const emptyNote = dom.historyList.querySelector('.history__empty');
  if (emptyNote) emptyNote.remove();
  dom.historyList.append(makeRow(entry));
  dom.historyList.scrollTop = dom.historyList.scrollHeight;
  applyTranscriptMode();
}

function clearList() {
  if (!dom.historyList) return;
  dom.historyList.replaceChildren();
}

/** One row of the feed: timestamp, text, and a per-entry "show in folder". */
function makeRow(entry, hitQuery) {
  const li = document.createElement('li');
  li.className = 'hist';
  li.tabIndex = 0;
  if (entry.path) li.dataset.path = entry.path;
  if (selectedEntry && sameEntry(selectedEntry, entry)) li.classList.add('hist--selected');

  const time = document.createElement('span');
  time.className = 'hist__time';
  time.textContent = stampFor(entry);

  const text = document.createElement('span');
  text.className = 'hist__text';
  if (hitQuery) {
    for (const part of highlight(String(entry.text || ''), hitQuery)) {
      if (typeof part === 'string') text.append(document.createTextNode(part));
      else {
        const mark = document.createElement('mark');
        mark.textContent = part.mark;
        text.append(mark);
      }
    }
  } else {
    text.textContent = entry.text || '';
  }

  const folder = document.createElement('button');
  folder.type = 'button';
  folder.className = 'hist__folder';
  folder.title = entry.path ? `Show ${entry.path} in folder` : 'Show in folder';
  folder.setAttribute('aria-label', 'Show in folder');
  // D6 — the SAME 16x16 stroke folder as `#reveal-button` in the tools row. This
  // used to be `\u{1F4C1}`, an emoji: its glyph, weight and vertical metrics were
  // whatever Windows' emoji font decided, next to a panel built out of hairline
  // SVGs.
  folder.append(icon('M1.5 4.2a1 1 0 0 1 1-1h3.1l1.3 1.4h5.6a1 1 0 0 1 1 1v6.2a1 1 0 0 1-1 1h-10a1 1 0 0 1-1-1z', 1.3));
  folder.addEventListener('click', (event) => {
    event.stopPropagation();
    select(entry);
    revealPath(entry.path);
  });

  li.append(time, text, folder);
  li.addEventListener('click', () => select(entry));
  li.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      select(entry);
    }
  });
  return li;
}

/**
 * An inline SVG icon from the panel's one icon set: 16x16, `currentColor`,
 * hairline stroke, no fill. `d` is the path, `width` the stroke width.
 */
function icon(d, width) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(NS, 'path');
  path.setAttribute('d', d);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'currentColor');
  path.setAttribute('stroke-width', String(width));
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('stroke-linejoin', 'round');
  svg.append(path);
  return svg;
}

function select(entry) {
  selectedEntry = entry;
  if (!dom.historyList) { markRevealState(); return; }
  for (const row of dom.historyList.querySelectorAll('.hist')) {
    const same = row.dataset.path && entry.path && row.dataset.path === entry.path
      && row.querySelector('.hist__text')
      && row.querySelector('.hist__text').textContent === (entry.text || '');
    row.classList.toggle('hist--selected', Boolean(same));
  }
  markRevealState();
}

// ---------------------------------------------------------------------------
// THE TWO SURFACES
// ---------------------------------------------------------------------------
// Owner, 2026-10-08: the global hotkey opens the LIVE CAPTIONS ONLY — a short strip — and the
// full column becomes something the owner opens on purpose. One document, two
// layouts, and the shell switches between them by setting ONE attribute:
//
//     document.body.dataset.surface = 'strip' | 'panel'
//
// `app/panel/surface.js` defines it; `panel.css` draws the difference; this
// file only BEHAVES differently. Two rules keep that honest:
//
//   * every surface-dependent decision asks `currentSurface()` — never a second
//     copy of the attribute name, so a grep for `data-surface` finds one place in
//     each file and the three can be diffed against each other;
//   * every control is bound ONCE and hidden by CSS on the surface it does not
//     belong to (`display: none` also takes it out of the tab order and the
//     accessibility tree, which `visibility`/`opacity` would not).
//
// `window.SottoSurfaces` is the shell-facing half of the contract; the exact
// wire names, sizes and expected log lines are in
// `_main/receipt-panel-two-surfaces.md`.

/** `'strip'` or `'panel'` — the document's own answer, never a guess. */
function currentSurface() {
  return window.SottoSurfaces ? window.SottoSurfaces.current() : 'panel';
}

/**
 * Switch the layout IN THIS DOCUMENT. The shell is expected to call
 * `bridge.setPanelSurface(name)` instead (it must resize the window in the same
 * breath — see `openFullPanel`), but this is what a shell without that call, a
 * browser, and the audit harness use.
 */
function setSurface(name) {
  if (window.SottoSurfaces) window.SottoSurfaces.set(name);
  applySurface();
  return currentSurface();
}

/** Wire the surface hooks the shell drives, and paint the surface we start in. */
function wireSurfaces() {
  if (window.SottoSurfaces) window.SottoSurfaces.onChange(applySurface);
  applySurface();
}

/**
 * Everything that differs BEHAVIOURALLY between the two surfaces, in one
 * function, so the difference is readable in one place.
 *
 * The transcript drawer keeps its state across a switch (it is the same DOM node
 * and `applyTranscriptMode` is not undone), so opening the panel from the strip
 * cannot reset a drawer the owner had opened or a search he had run.
 */
function applySurface() {
  const surface = currentSurface();
  // The placeholder's sentence is four lines of prose: correct on the panel,
  // longer than the strip's whole live box. The TITLE carries it in the strip so
  // the information is still on screen (a tooltip) instead of deleted.
  const body = dom.placeholder && dom.placeholder.querySelector('.captions__placeholder-body');
  if (body) body.title = surface === 'strip' ? body.textContent.trim() : '';
  applyPauseAvailability();
  applyLiveEnabled(liveEnabled, { silent: true });
  return surface;
}

/** The strip's three controls. Live toggle, Pause, Open panel — and no more. */
function wireStripControls() {
  if (dom.stripLiveButton) {
    dom.stripLiveButton.addEventListener('click', () => {
      applyLiveEnabled(!liveEnabled);
    });
  }
  if (dom.stripOpenButton) {
    dom.stripOpenButton.addEventListener('click', () => openFullPanel('strip-open'));
  }
  // ONE handler per pause control, bound from a class so the strip's button and
  // the panel's own button cannot drift apart; `wirePause` owns the dialog.
  for (const button of dom.pauseButtons) {
    button.addEventListener('click', () => openPauseConfirm(button));
  }
}

/**
 * The LIVE ON/OFF toggle — `bridge.setLiveEnabled(bool)`, a shell call that does
 * not exist yet (`sotto_webview.py` has no such method; see the receipt).
 *
 * The button is a REAL toggle: `aria-pressed` carries the state, the label says
 * it, and the paint is driven from the attribute so the eye and the screen
 * reader read the same fact. Turning live off is the owner's way to stop the
 * streaming engine WITHOUT unloading anything — which is why it is one click and
 * deliberately NOT the same two-step flow as Pause.
 *
 * When the shell has no `setLiveEnabled`, the toggle is NOT a lie: it is painted
 * inert, `aria-disabled="true"` and its title says the shell does not implement
 * it. The local state still flips, because the alternative — a control that does
 * nothing and says nothing — is the defect this panel has been bitten by before.
 */
function applyLiveEnabled(enabled, options) {
  liveEnabled = Boolean(enabled);
  const wired = typeof bridge === 'object' && bridge !== null
    && typeof bridge.setLiveEnabled === 'function';
  liveSupported = wired;

  if (dom.stripLiveButton) {
    dom.stripLiveButton.setAttribute('aria-pressed', liveEnabled ? 'true' : 'false');
    dom.stripLiveButton.setAttribute('aria-disabled', wired ? 'false' : 'true');
    dom.stripLiveButton.dataset.wired = wired ? 'true' : 'false';
    dom.stripLiveButton.title = liveEnabled
      ? (wired
        ? 'Live captions are on. Turn them off to stop the live engine without unloading it.'
        : 'Live captions are on. This shell does not implement setLiveEnabled() yet, so this switch cannot reach the engine.')
      : (wired
        ? 'Live captions are off. Turn them back on to resume the live engine.'
        : 'Live captions are shown as off. This shell does not implement setLiveEnabled() yet, so nothing was actually stopped.');
  }
  if (dom.stripLiveLabel) {
    dom.stripLiveLabel.textContent = liveEnabled ? 'Live on' : 'Live off';
  }
  if (dom.stripLiveButton && !liveEnabled) dom.stripLiveButton.dataset.state = 'off';
  else if (dom.stripLiveButton) delete dom.stripLiveButton.dataset.state;

  if (!options || options.silent !== true) {
    if (wired) {
      // The return value is a Promise in every shipped bridge; tolerate a
      // synchronous one, and report a rejection instead of swallowing it.
      const result = bridge.setLiveEnabled(liveEnabled);
      if (result && typeof result.then === 'function') {
        result.then((payload) => {
          const confirmed = payload && typeof payload.liveEnabled === 'boolean'
            ? payload.liveEnabled : liveEnabled;
          if (confirmed !== liveEnabled) applyLiveEnabled(confirmed, { silent: true });
        }).catch((err) => {
          setStatus('Live toggle refused: ' + errorText(err), '');
          setTimeout(() => applyLiveEnabled(!liveEnabled, { silent: true }), 0);
        });
      }
    }
  }
  updateStripState();
}

/** The strip's status: a dot and ONE word. See `updateStripState`. */
function updateStripState() {
  if (!dom.stripState) return;
  const kind = statusSnapshot.kind;
  let word;
  let state;
  if (paused) {
    word = 'Paused';
    state = '';
  } else if (!liveEnabled) {
    word = 'Live off';
    state = '';
  } else if (kind === 'error') {
    word = 'Error';
    state = 'error';
  } else if (kind === 'live') {
    word = 'Live';
    state = 'live';
  } else {
    word = statusSnapshot.text ? 'Working' : 'Starting';
    state = '';
  }
  if (dom.stripWord) dom.stripWord.textContent = word;
  dom.stripState.classList.toggle('is-live', state === 'live');
  dom.stripState.classList.toggle('is-error', state === 'error');
  // The full sentence is one hover away — and the strip never loses it while
  // `#status-text` stays in the DOM for the read-back probes. The revive hint
  // is APPENDED rather than written instead, because this line runs on every
  // status and would otherwise erase the one place the strip says that it is
  // clickable.
  dom.stripState.title = (paused
    ? 'Paused — the engines are unloaded until you resume'
    : statusSnapshot.text || 'Sotto is starting') + ' — ' + REVIVE_HINT;
}

/** Open the FULL panel. `bridge.setPanelSurface('panel')` resizes in the shell. */
function openFullPanel(reason) {
  if (bridge && typeof bridge.setPanelSurface === 'function') {
    bridge.setPanelSurface('panel', reason);
    return;
  }
  // No shell call: switch the layout here (a browser, the harness, or a shell
  // that has not ported it yet). The strip is NOT short until the window is.
  setSurface('panel');
}

// ---------------------------------------------------------------------------
// THE PAUSE FLOW — two steps, and the second step says the honest thing
// ---------------------------------------------------------------------------
// Pause means UNLOAD (owner, 2026-10-08): the live engine and the background
// transcript go away, RAM and CPU come back, and resuming costs a model load.
//
// The confirmation exists because of what the OWNER said it must carry, verbatim
// intent: pausing is not necessary for performance — the background transcript is
// extremely light. So the dialog informs, with Cancel focused, and never nags.
//
// The panel cannot unload anything itself: it calls `bridge.pause({reason})` and
// the SHELL unloads. That call does not exist yet, so its absence is stated in
// the dialog BEFORE the owner presses anything and in the confirm button's own
// label, rather than being discovered as a no-op afterwards.

function wirePause() {
  applyPauseAvailability();
  if (dom.pauseCancelButton) {
    dom.pauseCancelButton.addEventListener('click', () => closePauseConfirm());
  }
  if (dom.pauseConfirmButton) {
    dom.pauseConfirmButton.addEventListener('click', () => confirmPause());
  }
  if (dom.pauseDialog) {
    // Escape closes the modal natively, which fires `cancel` BEFORE the dialog
    // is closed; putting focus back and clearing the local state is all that is
    // left to do here.
    dom.pauseDialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      closePauseConfirm();
    });
  }
}

/** Paint whether this shell can actually pause, and say so where the owner looks. */
function applyPauseAvailability() {
  const wired = typeof bridge === 'object' && bridge !== null
    && typeof bridge.pause === 'function';
  pauseSupported = wired;

  for (const button of dom.pauseButtons) {
    button.dataset.wired = wired ? 'true' : 'false';
    // Not `disabled`: the button's job is to OPEN the dialog, and the dialog is
    // where the owner finds out what this shell can and cannot do. `aria-disabled`
    // is the honest announcement without making it unreachable.
    button.setAttribute('aria-disabled', wired ? 'false' : 'true');
    button.title = wired
      ? 'Pause — unload the live and background engines (asks first)'
      : 'Pause — this shell does not implement bridge.pause() yet';
  }
  if (dom.pauseConfirmButton) {
    const label = wired ? 'Pause and unload' : 'Pause — not available in this shell yet';
    dom.pauseConfirmButton.textContent = label;
    dom.pauseConfirmButton.disabled = !wired;
    dom.pauseConfirmButton.title = wired
      ? 'Unload the live and background engines now'
      : 'This shell has no bridge.pause(), so there is nothing to unload: the panel will not pretend it paused';
  }
  if (dom.pauseShellNote) {
    const note = wired
      ? ''
      : 'This build cannot pause yet. The panel has no bridge.pause() to call, so '
        + 'the engines keep running and nothing will be unloaded.';
    dom.pauseShellNote.textContent = note;
    dom.pauseShellNote.hidden = note === '';
  }
}

// ---------------------------------------------------------------------------
// THE STATUS IS A REPAIR CONTROL — one click revives the WHOLE pipeline
// ---------------------------------------------------------------------------
// The owner's ruling, verbatim (2026-10-08): *"e o botao de error ou de idle sei
// que, ao clicar, deve fazer a pipeline inteira ser revivida, se nao tiver
// funcionando"*. Both status surfaces come with it: the panel's footer
// (`#status`) and the strip's own state (`#strip-state`). One click posts
// `bridge.revive()` and the SHELL does the killing and the respawning
// (`SottoShell.revive_worker`) — the panel never spawns anything itself.
//
// IT IS UNCONDITIONAL, AND THAT IS THE FEATURE. There is no health test here
// that could answer "you do not need this": the owner is looking at the screen
// and this is a repair button, so the only thing standing between him and a
// fresh worker is the model load. That price is stated in the element's own
// `title` BEFORE he clicks, and the click always goes through.
//
// THE WIRING IS DONE FROM JS AND NOT FROM THE MARKUP. `cursor`, `role`,
// `tabindex` and the listeners are all set here for two reasons: the status has
// to LOOK pressable and be reachable by keyboard or the control only exists for
// whoever already knew it was there, and `panel.html`/`panel.css` belong to
// another lane in this same session — a control the module cannot see is a
// control it cannot keep honest about.
//
// The mirror image of `wirePause` above: that one has to say what this shell
// CANNOT do, and so does this one. A shell with no `bridge.revive()` gets the
// sentence instead of a silent no-op.

/** Show the footer's sentence even though the state is not an error. */
function paintReviveSentence(sentence) {
  // `setStatus` KEEPS THE SENTENCE OFF THE SCREEN unless the state is `error` —
  // and it does not merely clip it, it writes an EMPTY STRING into the element
  // (`dom.statusText.textContent = paintsText ? text : ''`). So a repair that
  // only removed the clip class painted NOTHING AT ALL: the owner would click
  // the dead status and watch the footer go blank instead of saying it is
  // restarting. Measured — ARM P of `_main/revive-pipeline-oracle.py` caught the
  // empty footer on its first green-looking run, which is why the text is
  // written HERE, explicitly, and the class comes off with it. No stylesheet is
  // touched (this is the class `panel.css` already has for exactly this job) and
  // the next `setStatus` from the shell puts the icon back.
  const el = dom.statusText;
  if (!el) return;
  el.textContent = sentence;
  el.classList.remove('status__text--offscreen');
}

/** Has this shell ported the repair control? */
function reviveSupported() {
  return typeof bridge === 'object' && bridge !== null
    && typeof bridge.revive === 'function';
}

/** One click on the status: ask the shell to revive the pipeline. */
function revivePipeline() {
  if (reviveInFlight) {
    // The shell refuses a second respawn in flight too (`REVIVE_REFUSED`).
    // Saying it here as well keeps the panel's own words true with no round
    // trip, and keeps the second click from looking like a broken button.
    const already = 'Already restarting the pipeline…';
    setStatus(already, 'busy');
    paintReviveSentence(already);
    return false;
  }
  if (!reviveSupported()) {
    // THE HONESTY RULE, the one `applyPauseAvailability` already follows in the
    // other direction: an absent capability is STATED, never simulated. `busy`
    // and not `error` because nothing has died — this build simply cannot do
    // it, and a red light over a missing function would be a second lie.
    const missing = 'This shell cannot restart the pipeline (no bridge.revive())';
    setStatus(missing, 'busy');
    paintReviveSentence(missing);
    return false;
  }
  reviveInFlight = true;
  // THE STICKY DEATH COMES OFF THE SCREEN HERE, and this is the point of the
  // click for most owners who will ever use it. The shell holds an error until
  // a CAPTION proves recovery (AGENTS.md makes that law, `panel-exit3-oracle`
  // gates it), so "Worker stopped (exit 3)" is exactly the screen he is looking
  // at when he asks the app to try again.
  const sentence = 'Restarting the pipeline…';
  setStatus(sentence, 'busy');
  paintReviveSentence(sentence);
  // The strip says the same thing in its one word, and `updateStripState` has
  // already cleared `is-error`/`is-live` for a non-error, non-live kind.
  if (dom.stripWord) dom.stripWord.textContent = 'Restarting';
  bridge.revive('panel-status');
  // `post` is fire-and-forget and the shell answers on its own thread, so there
  // is no reply to clear the flag with. A ceiling releases it instead: without
  // one, a shell that never answered would make the panel refuse every later
  // click with "already restarting" — a control bricked by its own guard.
  window.setTimeout(() => { reviveInFlight = false; }, 10000);
  return true;
}

/** Make the status clickable, on both surfaces, from JS only. */
function wireRevive() {
  const wired = reviveSupported();
  const targets = [dom.status, dom.stripState].filter(Boolean);
  for (const el of targets) {
    el.style.cursor = 'pointer';
    el.setAttribute('role', 'button');
    el.setAttribute('tabindex', '0');
    // The footer's title is nobody else's (the strip's is written by
    // `updateStripState`, which appends this same hint).
    el.title = wired ? REVIVE_TITLE : REVIVE_TITLE + ' — not in this shell yet';
    el.addEventListener('click', () => revivePipeline());
    el.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
        // Space scrolls by default, and a control that moves the page under the
        // reader is not a control.
        event.preventDefault();
        revivePipeline();
      }
    });
  }
}

/**
 * OPEN THE CONFIRMATION. Two steps, in-panel, and the DEFAULT FOCUS IS CANCEL:
 * pausing is the destructive and slow one (resuming reloads the model), while
 * cancelling is a no-op, so the safe action is the one a reflex Enter takes.
 */
function openPauseConfirm(trigger) {
  if (!dom.pauseDialog) {
    // An older shell without the dialog must not lose the capability silently:
    // the panel says what it can do instead of pretending the click worked.
    setStatus('Pause needs a confirmation dialog this panel does not have', '');
    return;
  }
  applyPauseAvailability();
  pendingFocusReturn = (trigger && typeof trigger.focus === 'function')
    ? trigger
    : (document.activeElement && document.activeElement !== document.body
      ? document.activeElement : null);
  try {
    if (typeof dom.pauseDialog.showModal === 'function') dom.pauseDialog.showModal();
    else dom.pauseDialog.setAttribute('open', '');
  } catch (err) {
    dom.pauseDialog.setAttribute('open', '');
  }
  if (dom.pauseCancelButton && typeof dom.pauseCancelButton.focus === 'function') {
    try { dom.pauseCancelButton.focus(); } catch (err) { /* focus stays where it was */ }
  }
}

function closePauseConfirm() {
  if (dom.pauseDialog && dom.pauseDialog.open) {
    try { dom.pauseDialog.close(); } catch (err) { dom.pauseDialog.removeAttribute('open'); }
  } else if (dom.pauseDialog) {
    dom.pauseDialog.removeAttribute('open');
  }
  const back = pendingFocusReturn;
  pendingFocusReturn = null;
  // Focus goes BACK where it came from, and only ever inside this page.
  if (back && typeof back.focus === 'function') {
    try { back.focus(); } catch (err) { /* the element went away; no focus is taken */ }
  }
}

/** Step two: the owner confirmed. Ask the shell to unload, and say what happened. */
function confirmPause() {
  if (!pauseSupported || typeof bridge.pause !== 'function') {
    // Reached only if the button was activated programmatically; the button is
    // disabled in this state and its label already says why.
    if (dom.pauseShellNote) {
      dom.pauseShellNote.textContent = 'This build cannot pause yet — there is no '
        + 'bridge.pause() to call, so nothing was unloaded.';
      dom.pauseShellNote.hidden = false;
    }
    return;
  }
  let result = null;
  try {
    result = bridge.pause({ reason: 'panel-confirm' });
  } catch (err) {
    closePauseConfirm();
    setStatus('Pause failed: ' + errorText(err), '');
    return;
  }
  closePauseConfirm();
  if (result && typeof result.then === 'function') {
    result.then((payload) => {
      const ok = !payload || payload.paused !== false;
      if (!ok) {
        setStatus('The shell refused to pause', 'error');
        return;
      }
      setPaused(true, payload && payload.text ? String(payload.text) : null);
    }).catch((err) => {
      setStatus('Pause refused: ' + errorText(err), 'error');
    });
    return;
  }
  setPaused(true, null);
}

/**
 * The paused LOOK, on both surfaces. It does not claim the engines are gone —
 * only the shell can know that — it says the panel asked and is not transcribing.
 */
function setPaused(value, text) {
  paused = Boolean(value);
  if (dom.panel) dom.panel.classList.toggle('is-paused', paused);
  // The paused state is reported by the strip's one word. `setStatus` below
  // carries it into the snapshot that word reads, so one repaint is enough.
  if (paused) setStatus(text || 'Paused — engines unloaded', '');
  updateStripState();
}

/** Ask the OS file manager to open the entry's file, or the root when null.
 *  THE ONLY "show in folder" AFFORDANCE NOW, on both surfaces: the transcript
 *  bar's path button (`#history-root`) and the per-line button in the drawer
 *  both call this. The deleted HUD's duplicate button called it too. */
function revealPath(path) {
  if (!historyApi || !historyApi.reveal) {
    setHistoryNote('Show in folder unavailable: this shell has no transcript store');
    return;
  }
  historyApi.reveal(path || null);
  setHistoryNote(path ? 'Opening ' + path : 'Opening the transcript folder');
}

async function runSearch(rawQuery) {
  const query = String(rawQuery == null ? '' : rawQuery).trim();
  if (!query) {
    searchQuery = '';
    searchHits = [];
    if (dom.searchClear) dom.searchClear.hidden = true;
    setHistoryNote('');
    renderFeed();
    return;
  }
  if (!historyApi || !historyApi.search) {
    setHistoryNote('Search unavailable: this shell has no transcript store');
    return;
  }
  if (!canonicalProducer) {
    // D1 — the box is disabled for this reason, and a programmatic submit
    // (a probe, or a click on the Search button) gets the same sentence instead
    // of an empty result set that looks like "no matches".
    setHistoryNote('Search is off — nothing writes the transcript yet.');
    return;
  }
  searchQuery = query;
  if (dom.searchClear) dom.searchClear.hidden = false;
  try {
    const r = await historyApi.search(query, 200);
    searchHits = normaliseEntries(r, 'hits');
    renderSearchResults(query, searchHits);
  } catch (err) {
    setHistoryNote('Search failed: ' + errorText(err));
  }
}

function renderSearchResults(query, hits) {
  if (!dom.historyList) return;
  clearList();
  const list = Array.isArray(hits) ? hits : [];
  if (!list.length) {
    const empty = document.createElement('li');
    empty.className = 'history__empty';
    empty.textContent = `No transcript matches “${query}”.`;
    dom.historyList.append(empty);
    setHistoryNote(`0 matches for “${query}”`);
    return;
  }
  for (const hit of list) dom.historyList.append(makeRow(hit, query));
  setHistoryNote(`${list.length} match${list.length === 1 ? '' : 'es'} for “${query}”`);
  dom.historyList.scrollTop = 0;
}

// -- small helpers ----------------------------------------------------------

function normaliseEntries(result, key) {
  if (Array.isArray(result)) return result;
  if (result && Array.isArray(result.entries)) return result.entries;
  if (key && result && Array.isArray(result[key])) return result[key];
  if (result && Array.isArray(result.hits)) return result.hits;
  return [];
}

function matches(text, query) {
  return String(text || '').toLowerCase().indexOf(query.toLowerCase()) >= 0;
}

/** Split `text` into plain runs and {mark} runs for the first match of `query`. */
function highlight(text, query) {
  const at = text.toLowerCase().indexOf(String(query).toLowerCase());
  if (at < 0) return [text];
  return [text.slice(0, at), { mark: text.slice(at, at + query.length) }, text.slice(at + query.length)];
}

function sameEntry(a, b) {
  return (a.path || '') === (b.path || '') && (a.time || '') === (b.time || '')
    && (a.text || '') === (b.text || '');
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

function clockTime() {
  const d = new Date();
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

function todayStamp() {
  const d = new Date();
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/** `HH:MM:SS` for today; `MM-DD HH:MM:SS` for an older day. */
function stampFor(entry) {
  const time = entry.time || '';
  if (entry.date && entry.date !== todayStamp()) return `${entry.date.slice(5)} ${time}`;
  return time;
}

function setHistoryNote(text) {
  if (!dom.historyStatus) return;
  const value = String(text == null ? '' : text).trim();
  dom.historyStatus.textContent = value;
  dom.historyStatus.hidden = value === '';
}

function errorText(err) {
  return err && err.message ? err.message : String(err);
}

// ---------------------------------------------------------------------------
// Status + controls + readiness (unchanged behaviour, new placeholders).
// ---------------------------------------------------------------------------

function wireStatus() {
  bridge.onStatus((payload) => {
    // F8 — ONE CLASSIFIER, NOT TWO.
    //
    // This used to re-derive the severity from the PROSE with
    // `/stopped|error|dead|no audio|no working/i`, a regex that cannot see this
    // worker's own vocabulary: `silent-device`, `device-exhausted`, and a bare
    // `done` with NO verdict all matched nothing, so a dead worker was painted
    // with the same neutral styling as warm-up. The shell already decides
    // (worker_status_kind, ported from the Electron bridge's STATE_MAP), so the
    // panel now BELIEVES it. Both shapes are accepted: the WebView2 shell sends
    // `{text, kind}`, the earlier Electron arm sends a bare string.
    const { text, kind } = statusPayload(payload);
    if (!text) return;

    // A status change is a natural sentence boundary: close the held tail so
    // the last words are not stranded when the worker pauses mid-thought.
    engine.flush('status-change');

    const state = statusKind(kind);
    // ONE place records what the shell said, so the strip's single word is
    // painted from that one fact (see `updateStripState`).
    statusSnapshot = { text, kind: kind || null };
    updateStripState();
    if (state === 'error') {
      // An error status keeps the SHELL'S TEXT as the headline — it is the
      // sentence that names the device and the numbers. The readiness copy must
      // never overwrite it.
      setStatus(text, 'error');
      showReadiness({ title: 'Not transcribing', body: text }, true);
      return;
    }
    if (state === 'live') {
      // Captions are flowing. The footer goes live; the placeholder is left
      // alone because readiness copy is only for the NEUTRAL states, and a real
      // caption has already put the placeholder away.
      setStatus(text, 'live');
      return;
    }
    // Neutral (the shell's `busy`, an empty kind, or a kind this panel does not
    // know): the footer carries the shell's sentence and the placeholder carries
    // the one honest warm-up state, with the measured seconds.
    setStatus(text, '');
    showReadiness(window.SottoFormulation.describeReadiness(Date.now() - pipelineStartedAt));
  });

  bridge.onGeometry((geometry) => {
    // The renderer is told the real slab size so CSS can match the window
    // instead of guessing, which is how a panel ends up misaligned on a
    // different monitor.
    if (geometry && geometry.width) {
      document.documentElement.style.setProperty('--panel-width', `${geometry.width}px`);
    }
  });
}

/**
 * Read ONE status event into `{text, kind}`.
 *
 *   `{text:'…', kind:'error'|'live'|'busy'}`  the WebView2 shell (the app)
 *   `'…'`                                     the Electron arm (a bare string)
 *
 * Anything else — a missing payload, a non-string text — is `{text:'', kind:null}`,
 * i.e. no state change, never a guess.
 */
function statusPayload(payload) {
  if (typeof payload === 'string') return { text: payload, kind: null };
  if (payload && typeof payload === 'object') {
    const text = typeof payload.text === 'string' ? payload.text : '';
    const kind = typeof payload.kind === 'string' ? payload.kind.trim().toLowerCase() : '';
    return { text, kind: kind || null };
  }
  return { text: '', kind: null };
}

/**
 * The shell's kind, VERBATIM: `'error'` -> error, `'live'` -> live, everything
 * else (its `'busy'`, an empty string, a word nobody taught this panel) ->
 * neutral. No prose is read here, and no word list is re-invented: the fallback
 * that classified by regex is the defect this replaces.
 */
function statusKind(kind) {
  if (kind === 'error') return 'error';
  if (kind === 'live') return 'live';
  return '';
}

/**
 * The "behind" chip in the live bar — OPTIONAL, and silent when unsupported.
 *
 * It is subscribed ONLY when the hosting shell exposes `onStats` (neither shell
 * does today, so this returns immediately and the chip never appears); the day
 * the shell measures queue drops or a decode rate under real time, the panel
 * lights up by itself. Fail-closed in the same way as the rest of this file: a
 * missing field is not a fact, so it cannot make the chip appear.
 */
/**
 * THE LEVEL CONSUMER — real data or nothing.
 *
 * `pushLevel` is fed ONLY by a payload that actually carries a level. A missing
 * field is not a measurement, so it cannot make the bars move; the fallback is
 * `LEVEL_FLOOR` and `data-level="none"`, which is the honest picture of a panel
 * that has not been told anything.
 *
 * The smoothing is the part that makes a wave readable: an INSTANT attack (a
 * transient must not be softened away) and a ~200 ms release, applied per
 * measurement rather than per frame, so the shape does not depend on the frame
 * rate.
 */
function pushLevel(peak, blocks) {
  const value = Number(peak);
  if (!Number.isFinite(value)) return;
  const now = (typeof performance !== 'undefined' && performance.now)
    ? performance.now() : Date.now();
  const dt = LEVEL.at === null ? 0 : Math.max(0, now - LEVEL.at);
  LEVEL.at = now;
  const clamped = Math.max(0, Math.min(1, value));
  if (clamped >= LEVEL.level || dt === 0) {
    LEVEL.level = clamped;
  } else {
    // Exponential release towards the new value; `dt` is the real gap between
    // measurements, so a slow feed releases proportionally.
    const k = 1 - Math.exp(-dt / LEVEL_RELEASE_MS);
    LEVEL.level = LEVEL.level + (clamped - LEVEL.level) * k;
  }
  LEVEL.hist[LEVEL.head] = LEVEL.level;
  LEVEL.head = (LEVEL.head + 1) % LEVEL.hist.length;
  LEVEL.n = Math.min(LEVEL.n + 1, LEVEL.hist.length);
  LEVEL.have = true;
  LEVEL.blocks = Number.isFinite(Number(blocks)) ? Number(blocks) : LEVEL.blocks;
  paintLevel();
}

/** The five bars, from the smoothed history. `scaleY` only: no relayout. */
function paintLevel() {
  // The frozen skin's own meter, fed from the SAME smoothed history our bars use.
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.level(LEVEL.have ? LEVEL.level : 0);
  }
  const bars = document.querySelectorAll('.chrome__meter i');
  if (!bars.length) return;
  const want = LEVEL.have ? 'live' : 'none';
  if (document.body.dataset.level !== want) document.body.dataset.level = want;
  if (!LEVEL.have) {
    // Nothing to paint: clear the properties so the CSS floor applies, and say
    // so once rather than on every call.
    for (const bar of bars) bar.style.removeProperty('--meter-h');
    return;
  }
  // Five bars, oldest-to-newest across the most recent fifth of the history, so
  // the row reads as a short envelope rather than five copies of one number.
  const span = Math.max(1, Math.floor(LEVEL.n / bars.length));
  for (let i = 0; i < bars.length; i += 1) {
    const back = (bars.length - 1 - i) * span;
    const idx = (LEVEL.head - 1 - back + LEVEL.hist.length * 2) % LEVEL.hist.length;
    const v = LEVEL.hist[idx];
    bars[i].style.setProperty('--meter-h', String(Math.max(LEVEL_FLOOR, v).toFixed(3)));
  }
}

/**
 * The stats channel, if this shell has one. NOT wired to anything today: the
 * shell exposes neither `onStats` nor `getStats`, so this returns immediately and
 * the bars stay at the floor. The day it lands, the wave fills by itself.
 *
 * A payload is trusted only for the fields it actually carries — `stats.peak`
 * absent means NO measurement, never a zero.
 */
function wireLevel() {
  if (typeof bridge.onStats !== 'function' && typeof bridge.getStats !== 'function') {
    if (document.body) document.body.dataset.level = 'none';
    return;
  }
  if (document.body) document.body.dataset.level = 'none';

  function take(raw) {
    let payload = raw;
    if (typeof payload === 'string') {
      try { payload = JSON.parse(payload); } catch { return; }
    }
    if (!payload || typeof payload !== 'object') return;
    const fields = payload.stats && typeof payload.stats === 'object' ? payload.stats : payload;
    pushLevel(fields.peak, fields.blocks);
  }

  if (typeof bridge.onStats === 'function') bridge.onStats(take);
  if (typeof bridge.getStats === 'function') {
    const pull = () => {
      try {
        const result = bridge.getStats();
        if (result && typeof result.then === 'function') result.then(take).catch(() => {});
        else take(result);
      } catch (err) { /* a stats read must never break the panel */ }
    };
    pull();
    setInterval(pull, 1000);
  }
}

function wireStats() {
  if (typeof bridge.onStats !== 'function' || !dom.statsChip) return;
  bridge.onStats((raw) => {
    let stats = raw;
    if (typeof stats === 'string') {
      try {
        stats = JSON.parse(stats);
      } catch {
        return; // an unreadable event is not a reason to claim anything
      }
    }
    if (!stats || typeof stats !== 'object') return;
    const drops = Number.isFinite(Number(stats.queue_drops)) ? Number(stats.queue_drops) : null;
    const rate = Number.isFinite(Number(stats.rate)) ? Number(stats.rate) : null;
    const behind = (drops !== null && drops > 0) || (rate !== null && rate < 1);
    if (!behind) {
      // Recovery is symmetric: the chip goes away when the numbers do.
      dom.statsChip.hidden = true;
      dom.statsChip.textContent = '';
      return;
    }
    const bits = [];
    if (drops !== null && drops > 0) bits.push(`${drops} dropped`);
    if (rate !== null && rate < 1) bits.push(`${rate.toFixed(2)}×`);
    dom.statsChip.textContent = `behind · ${bits.join(' · ')}`;
    dom.statsChip.title = 'The live path is not keeping up with real time '
      + '(queue drops, or a decode rate under 1×). Captions may lag the speaker.';
    dom.statsChip.hidden = false;
  });
}

/**
 * Paint the readiness state into the placeholder area — the one place the
 * owner looks before the first caption exists.
 */
function showReadiness(readiness, isError) {
  if (!dom.placeholder) return;
  const title = dom.placeholder.querySelector('.captions__placeholder-title');
  const body = dom.placeholder.querySelector('.captions__placeholder-body');
  // P1-3 (2026-10-08 audit): each of the five directions owns its empty state —
  // the mockups' `AGUARDANDO ÁUDIO…` / `· · · aguardando fala` are not one
  // string in five fonts. The readiness state (warming vs ready vs error) still
  // decides WHICH message, the theme decides the VOICE. Error keeps the shell's
  // own sentence: an error must name its cause, never wear a costume.
  const theme = (document.documentElement.dataset && document.documentElement.dataset.theme) || 'theme-1';
  const voices = {
    'theme-1': { warming: 'Warming up the teleprompter', ready: 'Ready — speak and the line flows' },
    'theme-2': { warming: 'STBY — warming up', ready: '● CAPTANDO — awaiting speech' },
    'theme-3': { warming: 'Preparing the draft', ready: 'Blank page — the draft begins as you speak' },
    'theme-4': { warming: 'Dimming the house', ready: '· · · awaiting the first line' },
    'theme-5': { warming: 'Powering the instrument', ready: 'ON — listening' },
  };
  const voice = voices[theme] || voices['theme-1'];
  if (title) title.textContent = isError ? readiness.title : (readiness.state === 'warming' ? voice.warming : voice.ready);
  if (body) body.textContent = readiness.body;
  dom.placeholder.classList.toggle('captions__placeholder--warming', !isError);
  if (dom.list && !dom.list.childElementCount) dom.placeholder.hidden = false;
}

/**
 * The ONE word a frozen skin's status badge shows.
 *
 * The design's own vocabulary for the case where it is TRUE — a mockup's
 * `listening` / `paused` badge says exactly what this state is — and plain words
 * for everything else. Never a number, never a confidence: this panel measures
 * neither, and `panel.js`'s own status line (which floats over the skin) is where
 * the worker's cause is printed in full.
 *
 * @param {'live'|'error'|''} state
 */
function skinStateWord(state) {
  if (state === 'live') return 'listening';
  if (state === 'error') return 'error';
  if (paused) return 'paused';
  if (!liveEnabled) return 'off';
  return 'idle';
}

/** @param {'live'|'error'|''} state */
function setStatus(text, state) {
  if (!text) return;
  // ── THE SENTENCE IS OFF THE SCREEN EXCEPT WHEN IT IS A DEATH ───────────────
  // The owner ruled, verbatim (2026-10-08): *"tira o 'receiving captions'. deixa
  // só um icone dinamico"* — the healthy state becomes an ICON that changes with
  // the state, not a phrase. `Receiving captions` was the phrase he named.
  //
  // THE ONE EXCEPTION IS AN ERROR, AND IT IS DELIBERATE: `AGENTS.md` makes it law
  // that the panel names the worker's own cause and the DEVICE ("the panel text
  // must name the device, and the death must survive the automatic restart until
  // a CAPTION proves recovery"), and `_main/panel-exit3-oracle.py` gates exactly
  // that. An icon cannot name a device, so an error still paints its sentence and
  // the icon turns red beside it. He asked for the phrase he sees all day to go;
  // he did not ask for a silent death. Stated in the receipt as an exception.
  const paintsText = state === 'error';
  if (dom.statusText) {
    dom.statusText.textContent = paintsText ? text : '';
    // VISUALLY hidden, not `hidden`: the sentence is the only accessible name of
    // this state, and `hidden` would take it out of the accessibility tree too. The
    // clip rule in `panel.css` costs no layout and keeps a screen reader able to
    // read what the icon means.
    dom.statusText.classList.toggle('status__text--offscreen', !paintsText);
  }
  if (dom.statusDot) dom.statusDot.dataset.state = state || '';
  if (dom.status) {
    dom.status.classList.toggle('status--live', state === 'live');
    dom.status.classList.toggle('status--error', state === 'error');
  }
  // THE SAME FACT, IN A PLACE THE WHOLE SLAB CAN SEE (2026-10-08). The per-theme
  // state words (`LENDO`/`PAUSA`, `REC`/`STBY`, `ON`/`OFF`, `OUVINDO`/`PAUSA`)
  // live in the header AND in the footer, and `status--live` is a class on the
  // footer alone — CSS cannot select a header from a sibling's class. Mirroring
  // the SAME `state` argument onto `<body data-state>` is one write, adds no
  // second source of truth (it is literally this argument), and is what lets
  // every direction's own indicator light up. Absent/unknown state is the empty
  // string, so "no state" is a value and never a stale one.
  document.body.dataset.state = state || '';
  // The panel's OWN statuses land in the same snapshot the shell's do: the strip
  // would otherwise keep showing a stale shell sentence after Clear.
  statusSnapshot = { text, kind: state || null };
  updateStripState();
  // ── THE STATE WORD ON A FROZEN SKIN ───────────────────────────────────────
  // The design's own badge is a real slot with the design's own typography; what
  // goes in it is OUR state, in the design's own vocabulary for the one case where
  // the design's word is true ("listening") and in plain words for the rest. No
  // number and no confidence is ever printed there — see `skin-host.js`.
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.status({ word: skinStateWord(state), state: state || '' });
  }
  bridge.statusApplied(text);
}

function wireControls() {
  // Click-through is on for the transparent margin; turn it off while the
  // pointer is over the slab so these buttons are actually clickable.
  // Guarded: a harness or an older markup without #panel/#hide-button must not
  // throw here — that throw aborts the whole init block with a blank panel.
  const setInteractive = (active) => bridge.setPointerInteractive(active);
  if (dom.panel) {
    dom.panel.addEventListener('mouseenter', () => setInteractive(true));
    dom.panel.addEventListener('mouseleave', () => setInteractive(false));
  }

  if (dom.hideButton) dom.hideButton.addEventListener('click', () => bridge.hide());

  // TWO HANDLERS USED TO LIVE HERE. Both controls were removed from `panel.html` by
  // the owner, and both handlers went with them in the SAME edit — `wireControls` is
  // called once at module init, so a surviving `dom.clearButton.addEventListener`
  // would have been a `TypeError` on every launch with a blank panel and no captions.
  //
  //  • QUIT — the capability is NOT lost. `bridge.quit()` is still reachable: the tray
  //    menu carries "Quit Sotto" (the `ID_TRAY_QUIT` item in
  //    `app/webview/sotto_webview.py`) and `_main/tray-quit-probe.py` is the probe
  //    that established it. The panel can therefore still close the app.
  //
  //  • CLEAR — the capability IS unreachable, and this is the honest cost of the
  //    removal rather than a claim that nothing was lost. It was the ONLY caller of
  //    `engine.reset()`; the body that went with it also did `retireProvisional()`,
  //    dropped `holdTimer`, emptied `#caption-list`, reset `committedByStart`,
  //    restored the placeholder and told the shell via `bridge.clearApplied(0)`.
  //    Nothing else calls `engine.reset()` and there is no tray equivalent, so after
  //    this edit the live box can only be emptied by the worker's own `final:true`
  //    line boundary. Reported to the owner, not hidden: receipt §11.
}

/** Tell main the page is painted and what it is showing. */
function announceReady() {
  if (!dom.placeholder || !dom.list) return;
  const placeholder = dom.placeholder.textContent.replace(/\s+/g, ' ').trim();
  bridge.ready({
    captions: dom.list.childElementCount,
    placeholder,
    hasBridge: true,
  });
}

// ---------------------------------------------------------------------------
// THE DIRECTION'S OWN CLOCK (2026-10-08)
// ---------------------------------------------------------------------------
// `bcast` prints a timecode in its header (`CH·01` … `HH:MM:SS` in the mockup).
// A clock that never ticks is a screenshot, so the elements the markup marks
// `data-chrome-clock` are repainted once a second.
//
// THE COST IS DELIBERATE AND TINY: one `setInterval` at 1 Hz writing a 8-char
// string into 0 or 1 elements (`display: none` blocks are not in the document's
// painted tree, but `textContent` is still written to them — so the write is
// gated on the element being the ACTIVE theme's, which is one `offsetParent`
// read per second). It is NOT a rAF loop and it animates nothing:
// `_main/_panel-anim-cost-arm.py` measures the panel with it running.
//
// It is armed HERE, at the bottom of the module, and not in the init block: it
// touches no state the init block owns, and arming it later cannot delay the
// first paint.
(function startChromeClock() {
  const nodes = document.querySelectorAll('[data-chrome-clock]');
  if (!nodes.length) return;
  const tick = () => {
    const now = clockTime();
    for (const el of nodes) {
      // `offsetParent === null` is the cheap "this element is not rendered"
      // test (`display: none` anywhere up the tree). A hidden direction's clock
      // is not worth a DOM write.
      if (el.offsetParent === null) continue;
      if (el.textContent !== now) el.textContent = now;
    }
  };
  tick();
  setInterval(tick, 1000);
}());
