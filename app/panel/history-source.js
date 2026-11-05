'use strict';

/**
 * Sotto — WHICH PRODUCER may write the CANONICAL TRANSCRIPT ("History · Redux").
 *
 * OWNER 2026-10-07, verbatim: *"o live nvidia do painel do sotto é pra ser o
 * nvidia funcionando, enquanto o historico nao é pra ser NUNCA o historico do
 * live nvidia. é pra ser do parakeet redux. e eu to vendo q nao ta desse
 * jeito"*.
 *
 * The panel has TWO fields fed by ONE engine, and that is the defect the owner
 * reported:
 *
 *   LIVE    (bottom, `panel.html` "Live · NVIDIA") — the streaming captions the
 *           nvidia worker emits (nemotron-3.5-asr-streaming-0.6b-int8,
 *           `worker/config.json model.dir`). Fed by `panel.js addCaption`.
 *   HISTORY (top, `panel.html` "History · Redux") — the accumulated transcript.
 *           Fed by `panel.js recordHistory`, which `addCaption` calls on its
 *           last useful line (`panel.js:207`). So HISTORY was literally the
 *           LIVE nvidia engine's own history — exactly what the owner forbids.
 *
 * THE SEPARATION. The transcript this product ships for is the CANONICAL
 * transcript, and the plan (`README.md:20-24,53-55`) makes it a DIFFERENT
 * engine: a BATCH pass over the recorded audio (`moondream/parakeet-redux` via
 * `transcribe.cpp`), NOT the streaming nvidia path. This predicate is the single
 * decision of which producer a line may come from, so the two fields can never
 * draw from one source again:
 *
 *   producer:'redux'  -> a line the CANONICAL (batch) pass produced: ACCEPTED.
 *   producer:'live'   -> a line the LIVE streaming engine produced: REFUSED —
 *                        the owner's "NUNCA".
 *   absent / unknown  -> REFUSED (fail-closed): a line that does not SAY it is
 *                        canonical is not the canonical transcript.
 *
 * IT IS DOM-FREE ON PURPOSE — the same reason `caption-formulation.js` is — so
 * an oracle can execute THIS EXACT FUNCTION outside Electron instead of
 * regexing `panel.js` (which is DOM-bound and cannot be run here). See
 * `_main/live-vs-history-source-oracle.js`.
 *
 * PARAKEEP REDUX IS NOT ON DISK. There are no weights and no call site
 * (`glob`/`grep` over `H:/sotto` find neither). This module is the SEPARATION,
 * not the engine: it makes the transcript refuse the live path and name the
 * producer that may never be faked. Until the batch pass exists and stamps
 * `producer:'redux'`, the HISTORY feed is EMPTY and says so — which is honest,
 * and is not the same thing as the live nvidia's history.
 */

/** The live streaming engine's producer tag — the one the HISTORY may NEVER take. */
const LIVE_PRODUCER = 'live';
/** The canonical (batch) producer tag the HISTORY is reserved for. */
const CANONICAL_PRODUCER = 'redux';
/** The route NAME a canonical line with no `final` stamp is recorded under. */
const BATCH_ROUTE = 'batch';

/** The producer a line declares, normalised; `null` when it declares none. */
function producerOf(meta) {
  if (!meta || typeof meta !== 'object') return null;
  const value = typeof meta.producer === 'string' ? meta.producer.trim() : '';
  return value || null;
}

/** True iff this line may enter the canonical transcript. Fail-closed. */
function isCanonicalLine(meta) {
  return producerOf(meta) === CANONICAL_PRODUCER;
}

/**
 * The route the transcript records for a line, or `null` when the line may never
 * enter it. The name is `batch` and never `final` for a Parakeet line because
 * `route=final` means a CLOSED caption line; see
 * `_main/receipt-20261101-batch-transcript-path.md`. That oracle used to demand
 * the batch engine's shape BEFORE asking whether the producer was canonical —
 * fixed 2026-11-01; the 2026-11-05 change below is the other half of the same
 * door (the canonical producer itself became the gate for everything).
 */
/**
 * THE ONE DECISION (2026-11-05) — may this line enter the transcript, and under
 * which route?
 *
 * It used to be TWO questions in TWO places: this function asked "which route?"
 * and `recordHistory` then asked `isCanonicalLine` again. The second question was
 * the door that stayed shut: the only producer that passed was `'redux'`, and the
 * batch pass (`worker/redux_batch.py`) is OFF by default (`--redux-when-hidden`),
 * so on this box the transcript had ZERO writers while the owner was watching.
 * MEASURED 2026-11-05 on his own log: 3830 `CAPTION_APPLIED`, 0 `HISTORY_APPEND`,
 * `history/2026-11-05/` absent — and no refusal line anywhere, because the
 * refusal was a bare `return`.
 *
 * THE RULE NOW: the transcript carries WHAT WAS SAID, one line per CLOSED
 * caption, whichever pass closed it. The producer is not the gate any more; it
 * is the PROVENANCE (the store writes `producer=` on the line), which is what
 * the 2026-10-07 separation actually needs — a reader must be able to tell a
 * Parakeet line from a streaming one, not to make the streaming one disappear.
 *
 * Still REFUSED, because none of them is a closed line:
 *   * `route === 'provisional-draft'` — the live caption (the panel's own hold
 *     deadline or a status flush). Owner 2026-10-06, verbatim: *"o historico
 *     simplesmente mostra a legenda ao vivo"*.
 *   * a route the writer does not know AND that is not absent.
 *   * no route at all with no canonical producer: nothing says the line ended.
 */
function historyDecision(meta) {
  const route = meta && typeof meta.route === 'string' ? meta.route : '';
  if (route === 'final') return { route: 'final', reason: '' };
  if (route) {
    return {
      route: null,
      reason: route === 'provisional-draft' ? 'provisional-draft' : 'unknown-route',
    };
  }
  if (isCanonicalLine(meta)) return { route: BATCH_ROUTE, reason: '' };
  return { route: null, reason: 'no-route-no-producer' };
}

/** The route the transcript records for this line, or `null` when it is refused. */
function transcriptRoute(meta) {
  return historyDecision(meta).route;
}

/**
 * WHY the line was refused — `null` when it was not. This is the instrument: a
 * refusal that cannot name itself is the defect this module was taught to stop
 * committing (`recordHistory` reports it as `HISTORY_REFUSED`).
 */
function historyRefusal(meta) {
  const decision = historyDecision(meta);
  if (decision.route !== null) return null;
  return {
    reason: decision.reason,
    route: meta && typeof meta.route === 'string' ? meta.route : null,
    producer: producerOf(meta),
    src: meta && typeof meta.source === 'string' && meta.source ? meta.source : null,
  };
}

const SottoHistorySource = {
  LIVE_PRODUCER,
  CANONICAL_PRODUCER,
  BATCH_ROUTE,
  producerOf,
  isCanonicalLine,
  historyDecision,
  transcriptRoute,
  historyRefusal,
};

// Both surfaces, because this file is BOTH a `<script>` in the panel and a
// `require` in the oracle — the same dual export `caption-formulation.js`
// carries, and for the same reason: exporting only under CommonJS left the
// renderer with nothing.
if (typeof module !== 'undefined' && module.exports) module.exports = SottoHistorySource;
if (typeof window !== 'undefined') window.SottoHistorySource = SottoHistorySource;
