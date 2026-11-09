"""Compact transcription-time context for the transcript history.

WHAT THIS ANSWERS (owner ask, 2026-11-09): months later, reading a transcript
line, "where did this audio come from and what was I looking at when it was
said?" -- without screenshots, screen recording, voice labels or credentials.

FIVE OPTIONAL FIELDS, in this order: `sourceApp` (the app whose audio was
tapped), `audioSource` (the worker's own source), `viewingApp`, `viewingTitle`
and `viewingUrl` (query, fragment and userinfo stripped; a YouTube `?v=` is the
one query kept, because it is the recall key).

CAPTURE IS AT TRANSCRIPTION TIME, NOT COMMIT TIME. `snapshot()` is called from
the worker's event arrival (`SottoShell.note_history_context`) keyed by the
line's `start=`, so a line committed seconds later still carries the context of
WHEN THE SPEECH HAPPENED; no meta is the commit-time fallback only.

ON DISK IT IS ONE VERSIONED TOKEN PER LINE: `ctx1=<body>` inside the line's
HTML comment, percent-encoded `letter:value` pairs joined by `|`. A line with no
context carries no token and a reader never inherits a neighbour's. The body is
capped at `MAX_TOKEN_CHARS`; the field that overflows is TRIMMED by whole
characters (a percent escape is never cut, the ORIGIN survives) and later fields
are dropped -- erasing it instead would let a 120-character CJK title take the
audio source with it (measured against the Node twin, which trims, 2026-11-09).

NOTHING HERE STARTS A PROCESS, OPENS A WINDOW, READS PIXELS OR TAKES INPUT.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import re
import threading
import time
from urllib.parse import parse_qs, quote, unquote, urlsplit

#: The API's field names, in the order the encoded token writes them.
CONTEXT_KEYS = ('sourceApp', 'audioSource', 'viewingApp', 'viewingTitle', 'viewingUrl')
#: One letter per field, so a line carries ~a dozen bytes when nothing changed.
_LETTERS = {'sourceApp': 'a', 'audioSource': 's', 'viewingApp': 'v',
            'viewingTitle': 't', 'viewingUrl': 'u'}
_BY_LETTER = {v: k for k, v in _LETTERS.items()}
#: Hard ceilings. A title or URL longer than this is noise in a transcript.
MAX_LEN = {'sourceApp': 64, 'audioSource': 96, 'viewingApp': 64,
           'viewingTitle': 120, 'viewingUrl': 300}
#: The encoded body's ceiling. A 120-character CJK title is 1 080 encoded
#: characters without it; the token is a compact annotation, not a second copy.
MAX_TOKEN_CHARS = 512
#: The marker's version. A reader that does not know it refuses the token.
VERSION = 'ctx1'
#: How long a foreground read is reused -- shorter than the gap between two
#: closed lines, long enough that a burst of finals costs one read.
_FOREGROUND_TTL_S = 0.5
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_TITLE_CHARS = 512
#: What a URL path keeps unescaped: the WHATWG parser's set, so both hosts
#: serialize the same bytes. `%` must stay safe or `%20` double-encodes.
_PATH_SAFE = "/%:@!$&'()*+,;=-._~[]"


def _text(value):
    """One bounded, printable, single-line string (or '').

    A CONTROL CHARACTER IS A WORD BREAK, not something to delete: dropping it
    joins the words around it (`page\\n2` -> `page2`), a different string from
    the Node twin's for the same input, and both write the same field.
    """
    if not isinstance(value, str):
        return ''
    cleaned = ''.join(' ' if (ch < ' ' or ch == '\x7f') else ch for ch in value)
    return ' '.join(cleaned.split())


def _url(value):
    """A bounded http(s) URL with query, fragment and userinfo REMOVED.

    The query is where a token or a session id lives; the one exception is a
    YouTube video id, which is the recall key. The path is percent-encoded as
    `new URL(...).pathname` does, so a raw space or a non-ASCII character
    serializes to the same bytes on both hosts (measured 2026-11-09).
    """
    raw = _text(value)
    if not raw:
        return ''
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ''
    scheme = (parts.scheme or '').lower()
    if scheme not in ('http', 'https'):
        return ''
    netloc = (parts.netloc or '').rsplit('@', 1)[-1].lower()
    if not netloc:
        return ''
    path = quote(parts.path or '', safe=_PATH_SAFE)
    query = ''
    if netloc in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        video = (parse_qs(parts.query).get('v') or [''])[0]
        if re.fullmatch(r'[A-Za-z0-9_-]{6,20}', video or ''):
            query = '?v=' + video
    # A bare host's trailing slash is not a recall key; a surviving `?v=` makes
    # the slash part of it (`https://www.youtube.com/?v=<id>`, same in Node).
    if query:
        path = path or '/'
    elif path == '/':
        path = ''
    return f'{scheme}://{netloc}{path}{query}'[:MAX_LEN['viewingUrl']]


def normalize(raw):
    """The one bounded shape every caller stores and every reader returns."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key in CONTEXT_KEYS:
        value = raw.get(key)
        if key == 'viewingUrl':
            value = _url(value)
        else:
            value = _text(value)
        if not value:
            continue
        out[key] = value[:MAX_LEN[key]]
    return out


def encode(context):
    """`{field: value}` -> the compact token body, or '' when there is nothing."""
    ctx = normalize(context)
    if not ctx:
        return ''
    parts = []
    used = 0
    for key in CONTEXT_KEYS:
        value = ctx.get(key)
        if not value:
            continue
        letter = _LETTERS[key] + ':'
        sep = 1 if parts else 0
        room = MAX_TOKEN_CHARS - used - sep - len(letter)
        if room < 0:
            break
        quoted = quote(value, safe='')
        if len(quoted) <= room:
            parts.append(letter + quoted)
            used += sep + len(letter) + len(quoted)
            continue
        # TRIMMED, NOT ERASED, by whole characters: cutting inside a percent
        # escape would make the token undecodable for every reader. The origin
        # comes first, so a pathological title still leaves it readable.
        while quoted and len(quoted) > room:
            value = value[:-1]
            quoted = quote(value, safe='')
        if quoted:
            parts.append(letter + quoted)
        break
    return '|'.join(parts)


def decode(token):
    """The compact token body -> `{field: value}`; unknown/oversized is dropped."""
    raw = str(token or '').strip()
    if not raw:
        return {}
    out = {}
    for part in raw.split('|'):
        letter, sep, value = part.partition(':')
        if not sep:
            continue
        key = _BY_LETTER.get(letter)
        if key is None:
            continue
        try:
            out[key] = unquote(value)
        except (ValueError, UnicodeError):
            continue
    return normalize(out)


def marker(encoded):
    """The exact token the writer puts inside the HTML comment ('' = omit)."""
    body = str(encoded or '').strip()
    return f'{VERSION}={body}' if body else ''


def token_in(line):
    """The context carried by one raw history line, as a dict ({} if none).

    Front-anchored: the writer puts `ctx1=` first inside the comment, before the
    free-text `reason`, so a `ctx1=` written into a reason is never selected.
    """
    match = re.search(r'<!--\s*' + VERSION + r'=(\S+)(?:\s|-->)', str(line or ''))
    return decode(match.group(1)) if match else {}


# --------------------------------------------------------------- foreground --

_foreground_lock = threading.Lock()
_foreground_cache = {'at': 0.0, 'value': {}}


def _process_basename(pid):
    """The image's basename for one pid, or ''. Read-only, microsecond cost."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return ''
    if pid <= 0 or os.name != 'nt':
        return ''
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD,
                                               ctypes.c_wchar_p,
                                               ctypes.POINTER(wt.DWORD)]
    k32.QueryFullProcessImageNameW.restype = wt.BOOL
    handle = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ''
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if not k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ''
        return os.path.basename(buf.value)
    except Exception:  # noqa: BLE001 -- an unreadable process is unnamed, not fatal
        return ''
    finally:
        try:
            k32.CloseHandle(handle)
        except Exception:  # noqa: BLE001
            pass


def app_name(target):
    """`sourceApp` from an app target: a pid, an image name, or ''."""
    if target is None or isinstance(target, bool):
        return ''
    if isinstance(target, (int, float)):
        return _text(_process_basename(int(target)))[:MAX_LEN['sourceApp']]
    raw = _text(str(target))
    if not raw:
        return ''
    if raw.isdigit():
        return _text(_process_basename(int(raw)))[:MAX_LEN['sourceApp']]
    return _text(os.path.basename(raw))[:MAX_LEN['sourceApp']]


def foreground():
    """`{viewingApp, viewingTitle}` for the window in front, cached briefly."""
    if os.name != 'nt':
        return {}
    now = time.monotonic()
    with _foreground_lock:
        if now - _foreground_cache['at'] <= _FOREGROUND_TTL_S:
            return dict(_foreground_cache['value'])
    value = {}
    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wt.HWND
        user32.GetWindowTextW.argtypes = [wt.HWND, ctypes.c_wchar_p, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
        user32.GetWindowThreadProcessId.restype = wt.DWORD
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            buf = ctypes.create_unicode_buffer(_TITLE_CHARS)
            got = user32.GetWindowTextW(hwnd, buf, _TITLE_CHARS)
            title = _text(buf.value if got > 0 else '')
            pid = wt.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            app = _process_basename(pid.value)
            if app:
                value['viewingApp'] = app[:MAX_LEN['viewingApp']]
            if title:
                value['viewingTitle'] = title[:MAX_LEN['viewingTitle']]
    except Exception:  # noqa: BLE001 -- a foreground read that fails names nothing
        value = {}
    value = normalize(value)
    with _foreground_lock:
        _foreground_cache['at'] = now
        _foreground_cache['value'] = value
    return dict(value)


def snapshot(meta=None, app_target=None):
    """The bounded context for ONE closed line, captured when it arrived.

    `meta.source` is the audio origin and `meta.context` an explicit object that
    wins per field; everything else is the bounded fallback (the per-app tap
    target and the foreground window). A URL comes only from the caller.
    """
    meta = meta if isinstance(meta, dict) else {}
    out = {}
    audio = _text(str(meta.get('source') or ''))
    if audio:
        out['audioSource'] = audio[:MAX_LEN['audioSource']]
    app = app_name(app_target)
    if app:
        out['sourceApp'] = app
    out.update(foreground())
    explicit = meta.get('context')
    if isinstance(explicit, dict):
        out.update(normalize(explicit))
    return normalize(out)


__all__ = ['CONTEXT_KEYS', 'VERSION', 'MAX_LEN', 'normalize', 'encode', 'decode',
           'marker', 'token_in', 'app_name', 'foreground', 'snapshot']
