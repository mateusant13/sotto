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

const SottoHistorySource = {
  LIVE_PRODUCER,
  CANONICAL_PRODUCER,
  producerOf,
  isCanonicalLine,
};

// Both surfaces, because this file is BOTH a `<script>` in the panel and a
// `require` in the oracle — the same dual export `caption-formulation.js`
// carries, and for the same reason: exporting only under CommonJS left the
// renderer with nothing.
if (typeof module !== 'undefined' && module.exports) module.exports = SottoHistorySource;
if (typeof window !== 'undefined') window.SottoHistorySource = SottoHistorySource;
