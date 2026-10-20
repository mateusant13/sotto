#!/usr/bin/env python3
"""THE DELTA OF THE DESIGN LANE -- one job, one fingerprint, one honest answer.

WHY THIS EXISTS (owner, 2026-10-20, verbatim: *"faz cache e teste incremental/delta
e etc pra tu parar de re rodar tudo do zero TODA HORA"*).

`intake-shots.py` re-rendered EVERY job of the design intake on EVERY
invocation: 100 demo prints + 44 theme prints, ~13 minutes of headless Edge,
to produce THE SAME PNGs. This module is the layer that lets the lane
re-render ONLY what moved.

THE FINGERPRINT
---------------
    fingerprint(job) = sha256 over, in a STABLE ORDER:
        url      the BYTES of the file the job's `url` points to
        src      the BYTES of every source file that feeds the render
        eval     the BYTES of the job's `eval` script
        param    the job's image parameters: w, h, dsf, keys, wait, after, clip
        out      the job's output path, and its outJson path

CONTENT, never mtime: a `touch` must NOT invalidate a job, and a rewrite with
the SAME bytes must not either. Changing the CONTENT of any input changes the
fingerprint, and therefore the job runs again.

THE TWO KINDS OF INPUT, AND WHY BOTH ARE NEEDED
------------------------------------------------
MEASURED 2026-10-20, on this box, with the product's own lane:

  * two consecutive `panel_measure.build()` calls produce BYTE-IDENTICAL
    trees -- 212 files, the same sha256 for each -- and a byte-identical
    `panel.html` (78 423 B, sha256 477b8219...). So the built document IS a
    stable fingerprint input, and it is hashed as the `url` target.
  * but the built document REFERENCES the stylesheets and the scripts next
    to it, and a change to `app/panel/panel.css` changes the PNG without
    changing one byte of the HTML. So the SOURCE files that feed the build
    are hashed too -- that is the `src` part, and `srcRoot` is where the
    lane says "the render reads this directory".

THE THEME SHEETS ARE NOT ALL GLOBAL
------------------------------------
`app/panel/themes/theme-<N>.css` is scoped to its own theme: MEASURED
2026-10-20, EVERY style rule of `theme-1.css` (100 of 100), `theme-2.css`
(108 of 108) and `theme-5.css` (103 of 103) carries `data-theme='theme-<N>'`
and NOT ONE selector part is unscoped. The remaining blocks are at-rules
(`@keyframes`, `@media`), and a `@keyframes` IS global: the name
`sotto-caret` is defined by all five sheets, and the last one loaded wins.

So for a render of `theme-2`, the sheet `theme-1.css` contributes only its
at-rules, and for a render of `theme-1` it contributes everything. A change
to `theme-2.css`'s own rules re-renders theme-2 and NOTHING else -- which is
what makes the delta worth having.

THE HONESTY RULE (this is the whole point; a cache that can lie is worse than
no cache)
------------------------------------------------------------------------------
A job is a HIT only when ALL of these hold:

    (a) there is an entry for this job's NAME in the state;
    (b) the fingerprint computed NOW equals the one recorded;
    (c) the output PNG still EXISTS and its sha256 is the recorded one;
    (d) if the job has an `outJson`: that JSON still EXISTS and its sha256 is
        the recorded one.

If ANY of them fails -> MISS, and the job runs again. A failure is NEVER
reused as if it were a pass.

A job with NO input at all has NO fingerprint, and therefore can NEVER be a
HIT: there is nothing that could invalidate it, so it cannot be trusted.

THE STATE
---------
    H:\sotto\_cache\shots-steps.json

one JSON object, one entry per job: the fingerprint, the output paths and
their sha256s, the result the run produced, and the timestamp. It is written
atomically (temp file + os.replace), so a crash mid-write cannot leave a half
state behind. A CORRUPT state file is not a crash: it is a MISS for every
job, and it is REPORTED -- a cache that was thrown away silently is a cache
the user does not know about.

THIS MODULE OPENS NOTHING: no browser, no window, no audio device, no
network. It reads files and writes one JSON file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_STATE = os.path.join(REPO, "_cache", "shots-steps.json")

STATE_VERSION = 1
_CHUNK = 1 << 20

#: the job parameters that change the IMAGE.
PARAM_KEYS = ("w", "h", "dsf", "keys", "wait", "after", "clip")

#: a theme sheet of the product: `themes/theme-<N>.css`.
_THEME_SHEET = re.compile(r"^themes/theme-(\d+)\.css$")

#: the two scope forms the theme generator writes.
_SCOPE_EXACT = re.compile(r"data-theme='([^']*)'")
_SCOPE_PREFIX = re.compile(r"data-theme\^='([^']*)'")


# ── the primitives ───────────────────────────────────────────────────────────

def sha256_bytes(data) -> str:
    """sha256 of a bytes/str blob."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    """sha256 of a file's BYTES. A missing file -> None (never an exception)."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            while True:
                block = fh.read(_CHUNK)
                if not block:
                    break
                h.update(block)
        return h.hexdigest()
    except (OSError, ValueError):
        return None


def url_target(url):
    """The LOCAL FILE a `file:///` url points to, or None.

    The url itself is NOT part of the fingerprint: the built document lives in
    a `tempfile.mkdtemp()` that is deleted at the end of the run, so its path
    changes every time. The CONTENT is what counts.
    """
    if not url or not isinstance(url, str):
        return None
    if not url.startswith("file:///"):
        return None
    path = url[len("file:///"):]
    for sep in ("#", "?"):
        path = path.split(sep, 1)[0]
    if not path:
        return None
    return path.replace("/", os.sep)


# ── the stylesheet reader (only for the theme sheets) ───────────────────────

def css_blocks(text):
    """(selector, block) for every TOP-LEVEL block of a stylesheet.

    Comments are dropped, and a block ends at the '}' that matches its '{',
    so a nested @media is ONE block and not many.
    """
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out = []
    i = 0
    n = len(body)
    while i < n:
        j = body.find("{", i)
        if j < 0:
            break
        selector = body[i:j].strip()
        depth = 1
        k = j + 1
        while k < n and depth:
            ch = body[k]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            k += 1
        out.append((selector, body[i:k]))
        i = k
    return out


def _scoped_to(selector, theme):
    """True when EVERY selector of the rule is scoped to `theme` and to
    nothing else. A rule with an unscoped selector part is NOT scoped."""
    parts = [p for p in selector.split(",") if p.strip()]
    if not parts:
        return False
    for part in parts:
        exact = _SCOPE_EXACT.findall(part)
        prefix = _SCOPE_PREFIX.findall(part)
        if not exact and not prefix:
            return False
        if exact and theme not in exact:
            return False
        if prefix and not any(theme.startswith(p) for p in prefix):
            return False
    return True


def css_global_part(path, own_theme):
    """The text of the parts of a stylesheet that can reach ANY theme: the
    at-rules and the rules that are not scoped to `own_theme`."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, ValueError):
        return None
    parts = []
    for selector, block in css_blocks(text):
        if selector.startswith("@") or not _scoped_to(selector, own_theme):
            parts.append(block)
    return "\n".join(parts)


def workdir_digests(root, theme=None):
    """[(label, sha256)] -- the inputs of a render, by CONTENT, or None when
    something could not be read.

    Every file of the workdir is an input of the render, EXCEPT the scoped
    rules of another theme's sheet: they cannot reach this theme (MEASURED:
    every style rule of `theme-<N>.css` is scoped to `data-theme='theme-<N>'`).
    The at-rules of that sheet ARE included for every theme, because a
    `@keyframes` is global.
    """
    rows = []
    try:
        walker = os.walk(root)
    except OSError:
        return None
    for base, dirs, files in walker:
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            match = _THEME_SHEET.match(rel)
            if match is not None and theme and ("theme-%s" % match.group(1)) != theme:
                text = css_global_part(path, "theme-%s" % match.group(1))
                if text is None:
                    return None
                rows.append(("src:" + rel, sha256_bytes(text)))
                continue
            digest = sha256_file(path)
            if not digest:
                return None
            rows.append(("src:" + rel, digest))
    rows.sort()
    return rows


# ── the fingerprint ──────────────────────────────────────────────────────────

def fingerprint(job):
    """The fingerprint of a job, or None when there is NOTHING to fingerprint.

    None means: this job can NEVER be a HIT.
    """
    if not isinstance(job, dict):
        return None
    target = url_target(job.get("url"))
    if not target or not os.path.isfile(target):
        return None
    parts = []
    digest = sha256_file(target)
    if not digest:
        return None
    parts.append(("url", digest))
    root = job.get("srcRoot")
    if root and os.path.isdir(root):
        rows = workdir_digests(root, job.get("theme"))
        if rows is None:
            return None
        parts.extend(rows)
    script = job.get("eval")
    if script:
        digest = sha256_file(script)
        if not digest:
            return None
        parts.append(("eval", digest))
    for key in PARAM_KEYS:
        parts.append(("param:" + key,
                      json.dumps(job.get(key), sort_keys=True, default=str)))
    parts.append(("out", str(job.get("out") or "")))
    parts.append(("outJson", str(job.get("outJson") or "")))
    out = hashlib.sha256()
    for label, value in parts:
        out.update(label.encode("utf-8"))
        out.update(b"\0")
        out.update(value.encode("utf-8"))
        out.update(b"\n")
    return out.hexdigest()


# ── the state on disk ────────────────────────────────────────────────────────

def load_state(path: str = DEFAULT_STATE):
    """(state, error). A CORRUPT file is an empty state plus an error string
    -- it is never an exception: a broken cache must not break the lane. The
    error is REPORTED, because a cache that was thrown away silently is a
    cache the user does not know about."""
    empty = {"version": STATE_VERSION, "jobs": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return empty, None
    except (OSError, ValueError) as exc:
        return empty, "state-unreadable: %s: %s" % (type(exc).__name__, exc)
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict):
        return empty, "state-malformed: no 'jobs' object"
    return data, None


def save_state(state, path: str = DEFAULT_STATE) -> bool:
    """Atomic write: a temp file + os.replace, so a crash mid-write cannot
    leave a half state behind. The directory is created if it is not there."""
    directory = os.path.dirname(path)
    tmp = path + ".tmp-%d" % os.getpid()
    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(state, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
        return True
    except OSError as exc:
        sys.stderr.write("shots-delta: cannot write %s: %s\n" % (path, exc))
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False


# ── the two verbs ────────────────────────────────────────────────────────────

def decide(job, entry, state, fp=None):
    """(hit, reason). THE HONESTY RULE lives here and nowhere else."""
    if entry is None and isinstance(state, dict):
        entry = (state.get("jobs") or {}).get(job.get("name"))
    if not isinstance(entry, dict):
        return False, "no-entry: this job was never recorded"
    if fp is None:
        fp = fingerprint(job)
    if not fp:
        return False, "no-input: a job with no input can never be trusted"
    if entry.get("fingerprint") != fp:
        return False, "fingerprint: the inputs changed"
    out = job.get("out")
    if not out or not os.path.isfile(out):
        return False, "shot-missing: %s" % out
    if sha256_file(out) != entry.get("out_sha256"):
        return False, "shot-changed: %s" % out
    out_json = job.get("outJson")
    if out_json:
        if not os.path.isfile(out_json):
            return False, "json-missing: %s" % out_json
        if sha256_file(out_json) != entry.get("outJson_sha256"):
            return False, "json-changed: %s" % out_json
    return True, "ok"


def record(job, result, state, fp=None):
    """(entry, reason). Records the job AS IT RAN.

    A job whose artefacts are not all there is NOT recorded: a failure is
    never reused as if it were a pass.
    """
    if fp is None:
        fp = fingerprint(job)
    if not fp:
        return None, "no-input: refusing to record a job with no input"
    out = job.get("out")
    if not out or not os.path.isfile(out):
        return None, "shot-missing: %s" % out
    out_json = job.get("outJson")
    if out_json and not os.path.isfile(out_json):
        return None, "json-missing: %s" % out_json
    entry = {
        "fingerprint": fp,
        "out": out,
        "out_sha256": sha256_file(out),
        "outJson": out_json or None,
        "outJson_sha256": sha256_file(out_json) if out_json else None,
        "result": result,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    state.setdefault("jobs", {})[job.get("name")] = entry
    state["version"] = STATE_VERSION
    return entry, "ok"


# ── the CLI (a convenience; the lane does not use it) ───────────────────────

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = DEFAULT_STATE
    for i, arg in enumerate(argv):
        if arg == "--state" and i + 1 < len(argv):
            path = argv[i + 1]
    state, err = load_state(path)
    if err:
        print("STATE UNREADABLE: %s" % err)
    jobs = state.get("jobs") or {}
    for name in sorted(jobs):
        entry = jobs[name]
        print("%-44s %s" % (name, (entry.get("timestamp") or "-")))
        print("    fingerprint : %s" % (entry.get("fingerprint") or "-"))
        print("    out         : %s" % (entry.get("out") or "-"))
        print("    out sha256  : %s" % (entry.get("out_sha256") or "-"))
        print("    outJson     : %s" % (entry.get("outJson") or "-"))
    print("jobs in the state: %d   state: %s" % (len(jobs), path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
