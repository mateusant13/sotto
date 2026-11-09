'use strict';

/**
 * The `ctx1=` token codec — the ONE format two hosts write.
 *
 * This module is the Node half of `app/webview/history_context.py`. Both arms
 * write the same transcript files, so a line must serialise to the SAME bytes no
 * matter which one wrote it: same field names, same bounds, same front-anchored
 * `ctx1=` token, same percent-encoding, same URL normalisation. The measured
 * divergences that created this file (2026-11-09) were each a line that read
 * differently depending on the writer:
 *
 *   - `encodeURIComponent` leaves `!'()*` raw where Python's `quote` escapes
 *     them, so a title carrying one of the five produced two different tokens;
 *   - Python DELETED a control character (`page\n2` -> `page2`) where the WHATWG
 *     parser joins nothing and Node kept the word break;
 *   - an oversized title made Python ERASE the field (taking the audio origin
 *     with it) where Node trimmed it.
 *
 * TWO EDGES ARE FIXED HERE, AND THE PYTHON TWIN IS THE CANONICAL READER
 * (measured 2026-11-09, `_main/history-context-oracle.py` parity arms):
 *
 *   - PERCENT DECODE. `decodeURIComponent` THROWS on a malformed escape
 *     (`%zz`, `%2`, a trailing `%`) and on an invalid UTF-8 run (`%E0%A4`), and
 *     the catch erased the whole field — the line lost its audio origin where
 *     Python's `unquote` keeps the literal text and replaces undecodable bytes
 *     with U+FFFD. Neither writer can emit those (`quote(value, safe='')` and
 *     `percentEncode` below only ever produce `%XX` with two hex digits), so
 *     they arrive from a hand-edited or corrupted line — exactly the line where
 *     dropping a field is the wrong answer. `percentDecode` mirrors
 *     `urllib.parse.unquote(value, 'utf-8', 'replace')`: valid escapes decode,
 *     a `%` that is not followed by two hex digits stays literal, and the
 *     joined bytes decode once, non-fatally.
 *   - WHITESPACE. `\s` is NOT Python's whitespace: it matches U+FEFF and not
 *     U+0085 (NEL), while `str.split()` does the opposite. Both characters are
 *     ordinary title bytes that either writer percent-encodes (`%C2%85`,
 *     `%EF%BB%BF`), so a window title carrying one read differently from each
 *     host. `collapseSpace` uses Unicode White_Space (the `str.split()` set)
 *     for BOTH the field value and the URL, so TAB/NEL/A0/2028 collapse to one
 *     space on both hosts and U+FEFF survives as data.
 *
 * The Electron arm has no WinAPI foreground read; it only accepts an EXPLICIT
 * `meta.context` and never invents one. The caller (`history-store.js`) owns the
 * file layout, the merge decision and the retention window.
 *
 * No dependency: no `node:fs`, no process — pure functions over strings.
 */

//: The API's field names, in the order the encoded token writes them.
const CONTEXT_KEYS = ['sourceApp', 'audioSource', 'viewingApp', 'viewingTitle', 'viewingUrl'];
//: One letter per field, so a line carries ~a dozen bytes when nothing changed.
const CONTEXT_LETTERS = { sourceApp: 'a', audioSource: 's', viewingApp: 'v', viewingTitle: 't', viewingUrl: 'u' };
const CONTEXT_BY_LETTER = Object.fromEntries(Object.entries(CONTEXT_LETTERS).map(([k, v]) => [v, k]));
//: Hard ceilings — the twin of `MAX_LEN`. A longer title or URL is noise.
const CONTEXT_MAX_LEN = { sourceApp: 64, audioSource: 96, viewingApp: 64, viewingTitle: 120, viewingUrl: 300 };
//: The encoded body's ceiling, in characters — the twin of `MAX_TOKEN_CHARS`.
const MAX_TOKEN_CHARS = 512;
//: The marker's version. A reader that does not know it refuses the token.
const VERSION = 'ctx1';

/**
 * Percent-encode EXACTLY as Python's `quote(value, safe='')`.
 *
 * `encodeURIComponent` leaves `!'()*` unescaped and the Python twin escapes
 * them, so a title carrying one of those five would produce a DIFFERENT token
 * on each host for the same line. The token is one format, not two, so the
 * difference is closed here by hand (measured 2026-11-09).
 */
function percentEncode(value) {
  return encodeURIComponent(String(value == null ? '' : value))
    .replace(/[!'()*]/g, (ch) => `%${ch.charCodeAt(0).toString(16).toUpperCase()}`);
}

//: Unicode White_Space, plus the four C0 separators Python also splits on:
//: exactly the `str.split()` set, and deliberately NOT `\s` (which carries
//: U+FEFF and lacks U+0085).
const PY_SPACE = '\\t\\n\\v\\f\\r \\u001c-\\u001f\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const PY_SPACE_RUN = new RegExp(`[${PY_SPACE}]+`, 'g');

/**
 * Collapse whitespace and strip it, byte-for-byte as Python's `_text` does.
 *
 * A control character is a WORD BREAK, not something to delete (`page\n2` ->
 * `page 2`), and the surviving whitespace set is Unicode White_Space: `\s`
 * would turn U+FEFF into a space (Python keeps it) and leave U+0085 alone
 * (Python splits on it). Also the trailing strip after a bounded slice is a
 * SPACE strip, not `.trim()`: JS `trim` eats U+FEFF, the Python twin keeps it.
 */
function collapseSpace(value) {
  return String(value == null ? '' : value)
    .replace(/[\u0000-\u001f\u007f]+/g, ' ')
    .replace(PY_SPACE_RUN, ' ')
    .replace(/^ +| +$/g, '');
}

const HEX2 = /^[0-9A-Fa-f]{2}$/;

/**
 * Percent-decode exactly as `urllib.parse.unquote(value, 'utf-8', 'replace')`.
 *
 * `decodeURIComponent` is the wrong instrument for a file a human can edit: it
 * throws on `%zz`, `%2`, a trailing `%` and on an invalid UTF-8 run, and the
 * caller would then erase the field. Python keeps the literal text and decodes
 * the byte stream once with `errors='replace'`. A string with no `%` at all is
 * returned untouched (`unquote` short-circuits before its ASCII encode), and a
 * non-ASCII character next to an escape makes `unquote` raise, which the
 * caller turns into "field omitted"; a lone U+DC80..U+DCFF is the
 * `surrogateescape` byte it encodes to.
 */
function percentDecode(value) {
  const text = String(value == null ? '' : value);
  if (!text.includes('%')) return text;
  const bytes = [];
  for (let i = 0; i < text.length;) {
    if (text[i] === '%' && HEX2.test(text.slice(i + 1, i + 3))) {
      bytes.push(parseInt(text.slice(i + 1, i + 3), 16));
      i += 3;
      continue;
    }
    const code = text.charCodeAt(i);
    if (code >= 0xdc80 && code <= 0xdcff) {
      bytes.push(code - 0xdc00);          // Python ascii+surrogateescape
    } else if (code > 0x7f) {
      throw new Error('non-ascii beside a percent escape');
    } else {
      bytes.push(code);
    }
    i += 1;
  }
  // `ignoreBOM` matters: the default decoder DROPS a leading U+FEFF, while
  // Python's utf-8 codec keeps it as data.
  return new TextDecoder('utf-8', { fatal: false, ignoreBOM: true })
    .decode(new Uint8Array(bytes));
}

/**
 * The longest prefix of `value` whose encoding fits in `room` characters.
 *
 * Trims by CODE POINT, never by encoded character: a percent escape is three
 * ASCII characters (`%3A`) and a cut inside one makes the token undecodable for
 * every reader, including the Python twin. `Array.from` splits a non-BMP
 * character into one element, so a lone surrogate can never be handed to
 * `encodeURIComponent` (which would throw). Returns '' when nothing fits.
 */
function fitEncoded(value, room) {
  if (room <= 0) return '';
  const chars = Array.from(String(value == null ? '' : value));
  let lo = 0;
  let hi = chars.length;
  let best = '';
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const candidate = percentEncode(chars.slice(0, mid).join(''));
    if (candidate.length <= room) {
      best = candidate;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return best;
}

/** One bounded, printable, single-line field value. */
function cleanContextValue(value, max) {
  // The slice is bounded by CODE POINT, like Python's `value[:MAX_LEN]`, and
  // WITHOUT a trailing `.trim()`: a UTF-16 slice would cut a surrogate pair in
  // half and `trim` would eat a U+FEFF the twin keeps.
  const chars = Array.from(collapseSpace(value));
  return chars.length > max ? chars.slice(0, max).join('') : chars.join('');
}

/**
 * A bounded http(s) URL with query, fragment and userinfo REMOVED.
 *
 * The query is where a token or a session id lives; the one exception is a
 * YouTube video id, which is the recall key. The path is parsed by WHATWG and
 * then bounded, and the trailing slash of a bare host is dropped, so both
 * readers return the same bytes (review D8, 2026-11-09).
 */
function normalizeUrl(value) {
  // Clean BEFORE parsing, exactly like the Python twin's `_text`: a control
  // character is a WORD BREAK there, while the WHATWG parser silently DELETES
  // a tab/newline and joins the words (`a\nb` -> `ab`). The same input must
  // reach the same path on both hosts.
  const raw = collapseSpace(value);
  if (!raw) return '';
  try {
    const parsed = new URL(raw);
    if (!['http:', 'https:'].includes(parsed.protocol)) return '';
    if (!parsed.hostname) return '';
    let pathname = parsed.pathname;
    let query = '';
    if (['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(parsed.hostname)) {
      const video = parsed.searchParams.get('v') || '';
      if (/^[A-Za-z0-9_-]{6,20}$/.test(video)) query = `?v=${video}`;
    }
    // The URL parser always yields `/` for a bare host; the Python twin writes
    // `https://example.com` and cross-reader parity requires the same bytes.
    if (pathname === '/' && !query) pathname = '';
    return cleanContextValue(`${parsed.protocol}//${parsed.host}${pathname}${query}`, CONTEXT_MAX_LEN.viewingUrl);
  } catch {
    return '';
  }
}

/** The bounded shape every caller stores and every reader returns. */
function normalizeContext(raw) {
  const out = {};
  if (!raw || typeof raw !== 'object') return out;
  for (const key of CONTEXT_KEYS) {
    // Normalise the URL BEFORE the bound: truncating first can cut a query the
    // normaliser is about to remove, which would make the same URL read
    // differently from the Python twin.
    const value = key === 'viewingUrl'
      ? normalizeUrl(raw[key])
      : cleanContextValue(raw[key], CONTEXT_MAX_LEN[key]);
    if (value) out[key] = value;
  }
  return out;
}

/** The compact token body -> `{field: value}`; unknown/oversized is dropped. */
function decodeContext(raw) {
  const out = {};
  const text = String(raw == null ? '' : raw).trim();
  if (!text) return out;
  for (const part of text.split('|')) {
    const cut = part.indexOf(':');
    if (cut <= 0) continue;
    const key = CONTEXT_BY_LETTER[part.slice(0, cut)];
    if (!key) continue;
    let value = part.slice(cut + 1);
    try {
      // NOT `decodeURIComponent`: it throws on a malformed escape and the field
      // would be erased. `percentDecode` is `unquote(..., 'replace')`, and a
      // field the Python twin cannot decode either is omitted on both hosts.
      value = percentDecode(value);
    } catch {
      continue;
    }
    value = key === 'viewingUrl'
      ? normalizeUrl(value)
      : cleanContextValue(value, CONTEXT_MAX_LEN[key]);
    if (value) out[key] = value;
  }
  return out;
}

/** `{field: value}` -> the compact token body, or '' when there is nothing. */
function encodeContext(ctx) {
  // Normalise first, like the Python twin's `encode`: the token is built from
  // the same bounded shape every reader returns, so a caller cannot smuggle an
  // unbounded or unparsed value into the file.
  const clean = normalizeContext(ctx);
  const fields = [];
  let used = 0;
  for (const key of CONTEXT_KEYS) {
    const value = clean[key];
    if (!value) continue;
    const letter = `${CONTEXT_LETTERS[key]}:`;
    const sep = fields.length ? 1 : 0;
    const room = MAX_TOKEN_CHARS - used - sep - letter.length;
    if (room < 0) break;
    const encoded = percentEncode(value);
    if (encoded.length <= room) {
      fields.push(letter + encoded);
      used += sep + letter.length + encoded.length;
      continue;
    }
    // THE FIELD THAT OVERFLOWS IS TRIMMED, NOT ERASED -- the twin of the Python
    // `encode` path. The origin comes first in the fixed order, so a
    // pathological title still leaves the audio source readable; everything
    // after it is dropped because the budget is spent.
    const fitted = fitEncoded(value, room);
    if (fitted) fields.push(letter + fitted);
    break;
  }
  return fields.length ? fields.join('|') : '';
}

/** The context carried by one raw history line, as an object ({} if none). */
function contextTokenIn(line) {
  // Front-anchored, like the Python twin: `ctx1=` is the first field after
  // `<!--`, so a `ctx1=` inside the free-text reason is never selected (D2).
  const match = /<!--\s*ctx1=(\S+)(?:\s|-->)/.exec(String(line || ''));
  return match ? decodeContext(match[1]) : {};
}

module.exports = {
  CONTEXT_KEYS,
  MAX_TOKEN_CHARS,
  VERSION,
  percentEncode,
  normalizeUrl,
  normalizeContext,
  encodeContext,
  decodeContext,
  contextTokenIn,
};
