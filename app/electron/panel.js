'use strict';

/**
 * Sotto — the panel renderer (v2: two sections).
 *
 * TOP    `#history`  the accumulated transcript ("redux"): a feed read back
 *                    from disk, searchable, with a "show in folder" button.
 * BOTTOM `#captions` the LIVE caption box: the streaming caption growing line
 *                    by line. This is the focus.
 *
 * The renderer owns the DOM and nothing else. Two things come from outside:
 *   * captions, through `window.sotto.onCaption` (the preload/WebView2 bridge);
 *   * the history store, through `window.sotto.history` (append/tail/search/
 *     reveal/root) — implemented by whichever shell is hosting the page.
 *
 * The history API is probed, never assumed: an older shell without it degrades
 * to a working live box and an explicit "history unavailable" note, instead of a
 * renderer that throws on load.
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
  // history feed
  historyList: document.getElementById('history-list'),
  historyRoot: document.getElementById('history-root'),
  historyStatus: document.getElementById('history-status'),
  revealButton: document.getElementById('reveal-button'),
  searchForm: document.getElementById('search-form'),
  searchInput: document.getElementById('search-input'),
  searchButton: document.getElementById('search-button'),
  searchClear: document.getElementById('search-clear'),
  // footer
  status: document.getElementById('status'),
  statusText: document.getElementById('status-text'),
  hideButton: document.getElementById('hide-button'),
  clearButton: document.getElementById('clear-button'),
};

const bridge = window.sotto;
/** The history store, or null when the hosting shell does not implement it. */
const historyApi = bridge && bridge.history ? bridge.history : null;

/**
 * When the pipeline started, so readiness can state the MEASURED warm-up
 * instead of implying the owner is looking at a sequence of failures.
 */
const pipelineStartedAt = Date.now();

/** No bridge means no captions can ever arrive; say so instead of looking idle. */
if (!bridge) {
  dom.status.classList.add('status--error');
  dom.statusText.textContent = 'Preload bridge missing — captions are impossible';
  dom.placeholder.querySelector('.captions__placeholder-title').textContent = 'Panel not wired';
  dom.placeholder.querySelector('.captions__placeholder-body').textContent =
    'window.sotto is undefined. The preload script did not run, so no caption can reach this panel.';
  setHistoryNote('History unavailable: no bridge');
} else {
  wireHistory();
  wireCaptions();
  wireStatus();
  wireControls();
  announceReady();
}

// ---------------------------------------------------------------------------
// Caption formulation. The TEXT decisions live in `caption-formulation.js`,
// which is DOM-free precisely so an oracle can run the real functions outside
// Electron; this block owns only the wiring and the rendering of what the
// engine decides.
// ---------------------------------------------------------------------------

const engine = window.SottoFormulation.createEngine({
  onCommit: (text, reason) => addCaption(text, reason),
  onProvisional: (text, isProvisional) => renderProvisional(text, isProvisional),
});

/**
 * Restarted on every caption. If it fires, the worker sent nothing for
 * COMMIT_MAX_HOLD_MS, so the held tail is committed rather than stranded —
 * the one situation where abandoning the hold is correct.
 */
let holdTimer = null;
function armHoldTimer() {
  clearTimeout(holdTimer);
  holdTimer = setTimeout(() => {
    holdTimer = null;
    engine.expireHold();
  }, window.SottoFormulation.COMMIT_MAX_HOLD_MS);
}

/**
 * The provisional line: one `<li>` whose text is REWRITTEN IN PLACE as the
 * hypothesis changes. It is never acknowledged as applied until it commits,
 * because a caption the model later contradicts is not a caption.
 */
function renderProvisional(text, isProvisional) {
  if (!text) return;

  dom.placeholder.hidden = true;
  dom.list.hidden = false;

  let line = dom.list.querySelector('.caption--provisional');
  if (!line) {
    line = document.createElement('li');
    line.className = 'caption';

    const time = document.createElement('span');
    time.className = 'caption__time';
    time.textContent = clockTime();

    const body = document.createElement('span');
    body.className = 'caption__text';
    line.append(time, body);
    dom.list.append(line);
    followNewestLine();
  }

  line.querySelector('.caption__text').textContent = text;
  line.classList.toggle('caption--provisional', Boolean(isProvisional));
  line.classList.toggle('caption--latest', !isProvisional);
}

/** Drop the provisional line: its words are now committed text. */
function retireProvisional() {
  const line = dom.list.querySelector('.caption--provisional');
  if (line) dom.list.removeChild(line);
}

function wireCaptions() {
  // `meta` carries the audio seconds. They are what let the engine tell a NEW
  // word from a RE-READ one, so they are not optional decoration.
  bridge.onCaption(({ text, meta }) => {
    // Any fragment at all means the stream is alive, so the previous deadline
    // is void before the engine decides anything.
    armHoldTimer();
    engine.ingest(String(text || '').trim(), meta || {});
  });
}

/** A committed caption line: final text, acknowledged, and recorded in history. */
function addCaption(text) {
  if (!text) return false;

  retireProvisional();
  dom.placeholder.hidden = true;
  dom.list.hidden = false;

  const line = document.createElement('li');
  line.className = 'caption';

  const time = document.createElement('span');
  time.className = 'caption__time';
  time.textContent = clockTime();

  const body = document.createElement('span');
  body.className = 'caption__text';
  body.textContent = text;

  line.append(time, body);
  dom.list.append(line);

  // Mark the newest line, drop the highlight from the previous one.
  const previous = dom.list.querySelector('.caption--latest');
  if (previous) previous.classList.remove('caption--latest');
  line.classList.add('caption--latest');

  while (dom.list.childElementCount > MAX_CAPTIONS) {
    dom.list.removeChild(dom.list.firstElementChild);
  }

  followNewestLine();
  updateLiveHint();
  recordHistory(text);
  bridge.captionApplied(text);
  setStatus('Receiving captions', 'live');
  return true;
}

/**
 * Follow the newest line, but only when already near the bottom: yanking the
 * view away from someone reading back is worse than a stale scroll.
 */
function followNewestLine() {
  const { scrollTop, scrollHeight, clientHeight } = dom.captions;
  const nearBottom = scrollHeight - scrollTop - clientHeight < 48;
  if (nearBottom) dom.captions.scrollTop = scrollHeight;
}

function updateLiveHint() {
  const n = dom.list.childElementCount;
  dom.captionsHint.textContent = n ? `${n} line${n === 1 ? '' : 's'}` : '';
}

// ---------------------------------------------------------------------------
// History — the top feed, its disk store, the search and the "show in folder".
// ---------------------------------------------------------------------------

/** Every entry held in the feed, oldest first. */
let historyEntries = [];
/** The entry currently selected (its file is what "Show in folder" opens). */
let selectedEntry = null;
/** Non-empty while the feed is showing SEARCH RESULTS instead of the feed. */
let searchQuery = '';
/** The result set backing the current search view. */
let searchHits = [];

function wireHistory() {
  dom.revealButton.addEventListener('click', () => {
    revealPath(selectedEntry && selectedEntry.path);
  });
  dom.historyRoot.addEventListener('click', () => revealPath(null));

  dom.searchForm.addEventListener('submit', (event) => {
    event.preventDefault();
    runSearch(dom.searchInput.value);
  });
  dom.searchClear.addEventListener('click', () => {
    dom.searchInput.value = '';
    runSearch('');
  });

  if (!historyApi) {
    setHistoryNote(
      'History unavailable: this shell has no history store (data not written)',
    );
    dom.revealButton.disabled = true;
    loadHistoryFromMemory();
    return;
  }

  historyApi
    .root()
    .then((r) => {
      const root = (r && r.root) || (typeof r === 'string' ? r : '');
      if (root) {
        dom.historyRoot.textContent = root;
        dom.historyRoot.title = `Open ${root}`;
      }
    })
    .catch(() => {});

  loadHistory();
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
    .catch((err) => setHistoryNote('History read failed: ' + errorText(err)));
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
function recordHistory(text) {
  if (!historyApi || !historyApi.append) {
    pushEntry({ time: clockTime(), text, path: null });
    return;
  }
  historyApi
    .append(text, { source: 'live' })
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
  appendFeedRow(entry);
}

function renderFeed() {
  clearList();
  if (!historyEntries.length) {
    const empty = document.createElement('li');
    empty.className = 'history__empty';
    empty.textContent = historyApi
      ? 'No history yet. Captions are appended here as they happen.'
      : 'No history store in this shell.';
    dom.historyList.append(empty);
    return;
  }
  for (const entry of historyEntries) dom.historyList.append(makeRow(entry));
  dom.historyList.scrollTop = dom.historyList.scrollHeight;
}

function appendFeedRow(entry) {
  const emptyNote = dom.historyList.querySelector('.history__empty');
  if (emptyNote) emptyNote.remove();
  dom.historyList.append(makeRow(entry));
  dom.historyList.scrollTop = dom.historyList.scrollHeight;
}

function clearList() {
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
  folder.textContent = '\u{1F4C1}';
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

function select(entry) {
  selectedEntry = entry;
  for (const row of dom.historyList.querySelectorAll('.hist')) {
    const same = row.dataset.path && entry.path && row.dataset.path === entry.path
      && row.querySelector('.hist__text')
      && row.querySelector('.hist__text').textContent === (entry.text || '');
    row.classList.toggle('hist--selected', Boolean(same));
  }
  dom.revealButton.disabled = false;
  dom.revealButton.title = entry.path
    ? `Show ${entry.path} in the OS file manager`
    : 'Show the history folder in the OS file manager';
}

/** Ask the OS file manager to open the entry's file, or the root when null. */
function revealPath(path) {
  if (!historyApi || !historyApi.reveal) {
    setHistoryNote('Show in folder unavailable: this shell has no history store');
    return;
  }
  historyApi.reveal(path || null);
  setHistoryNote(path ? 'Opening ' + path : 'Opening the history folder');
}

async function runSearch(rawQuery) {
  const query = String(rawQuery == null ? '' : rawQuery).trim();
  if (!historyApi || !historyApi.search) {
    setHistoryNote('Search unavailable: this shell has no history store');
    return;
  }
  if (!query) {
    searchQuery = '';
    searchHits = [];
    dom.searchClear.hidden = true;
    setHistoryNote('');
    renderFeed();
    return;
  }
  searchQuery = query;
  dom.searchClear.hidden = false;
  try {
    const r = await historyApi.search(query, 200);
    searchHits = normaliseEntries(r, 'hits');
    renderSearchResults(query, searchHits);
  } catch (err) {
    setHistoryNote('Search failed: ' + errorText(err));
  }
}

function renderSearchResults(query, hits) {
  clearList();
  if (!hits.length) {
    const empty = document.createElement('li');
    empty.className = 'history__empty';
    empty.textContent = `No history matches “${query}”.`;
    dom.historyList.append(empty);
    setHistoryNote(`0 matches for “${query}”`);
    return;
  }
  for (const hit of hits) dom.historyList.append(makeRow(hit, query));
  setHistoryNote(`${hits.length} match${hits.length === 1 ? '' : 'es'} for “${query}”`);
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
  bridge.onStatus((text) => {
    // A status change is a natural sentence boundary: close the held tail so
    // the last words are not stranded when the worker pauses mid-thought.
    engine.flush('status-change');

    // (c) ONE honest state during warm-up, carrying the measured seconds,
    // instead of a sequence of placeholders that each look like a different
    // failure. Only a real error keeps the error state.
    const readiness = window.SottoFormulation.describeReadiness(Date.now() - pipelineStartedAt);
    const errored = /stopped|error|dead|no audio|no working/i.test(String(text || ''));
    if (errored) {
      setStatus(String(text || ''), 'error');
      showReadiness({ title: 'Not transcribing', body: String(text || '') }, true);
      return;
    }
    setStatus(String(text || ''), '');
    showReadiness(readiness);
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
 * Paint the readiness state into the placeholder area — the one place the
 * owner looks before the first caption exists.
 */
function showReadiness(readiness, isError) {
  const title = dom.placeholder.querySelector('.captions__placeholder-title');
  const body = dom.placeholder.querySelector('.captions__placeholder-body');
  if (title) title.textContent = readiness.title;
  if (body) body.textContent = readiness.body;
  dom.placeholder.classList.toggle('captions__placeholder--warming', !isError);
  if (!dom.list.childElementCount) dom.placeholder.hidden = false;
}

/** @param {'live'|'error'|''} state */
function setStatus(text, state) {
  if (!text) return;
  dom.statusText.textContent = text;
  dom.status.classList.toggle('status--live', state === 'live');
  dom.status.classList.toggle('status--error', state === 'error');
  bridge.statusApplied(text);
}

function wireControls() {
  // Click-through is on for the transparent margin; turn it off while the
  // pointer is over the slab so these buttons are actually clickable.
  const setInteractive = (active) => bridge.setPointerInteractive(active);
  dom.panel.addEventListener('mouseenter', () => setInteractive(true));
  dom.panel.addEventListener('mouseleave', () => setInteractive(false));

  dom.hideButton.addEventListener('click', () => bridge.hide());
  dom.clearButton.addEventListener('click', () => {
    dom.list.replaceChildren();
    dom.list.hidden = true;
    dom.placeholder.hidden = false;
    updateLiveHint();
    bridge.clearApplied(0);
    setStatus('Cleared', '');
  });
}

/** Tell main the page is painted and what it is showing. */
function announceReady() {
  const placeholder = dom.placeholder.textContent.replace(/\s+/g, ' ').trim();
  bridge.ready({
    captions: dom.list.childElementCount,
    placeholder,
    hasBridge: true,
  });
}
