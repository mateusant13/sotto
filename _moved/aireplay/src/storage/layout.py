"""layout.py -- the deterministic on-disk layout of the clip store.

Every path in the store is a PURE FUNCTION of a `clip_id`, and a `clip_id` is a pure
function of (UTC start instant, sequence). Nothing about the layout lives only in the code
that wrote it: a reader re-derives the same directory from the id alone, and `walk_keys()`
rebuilds the whole index-key population from disk with no db and no in-memory state. That is
the property that survives a version bump -- see `READ_RULES`.

    <root>/
      layout.json                     the store's own version marker (written once)
      clips/
        2026/10/07/                   UTC, always -- the machine's TZ never moves a file
          20261007T130648Z-0001/      one directory per clip
            .partial                  PRESENT iff the clip is not committed. Its presence is
                                      the ONLY crash marker: it is written before a single
                                      media byte and removed after the key lands.
            clip.mp4                  the muxed artefact
            transcript.json           sidecar
            thumb.jpg                 sidecar
            key.json                  THE COMMIT MARKER -- the index key, written LAST

The commit rule is one atomic step: `key.json.tmp` -> `os.replace` -> `key.json`, then the
`.partial` marker is unlinked. A crash therefore leaves exactly one of two identifiable
states, never a half-committed dir:

    .partial + key.json    committed, marker not yet removed   -> FINISH  (drop the marker)
    .partial, no key.json  media written, commit never landed   -> DISCARD (the mp4 has no
                                                                    finished moov; it will
                                                                    not play)

Reconciliation lives in `retention.py`; the VOCABULARY it decides over is `classify()` here,
because the on-disk truth is this module's to state.

Imports only the stdlib, and nothing heavy: the ASR pins its thread pools before numpy loads
(`src/asr/__init__.py`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------------------------
# Constants.  Every one of these is a NAMED rule, because a path rule that only lives in the
# expression that builds the path is the bug this module exists to prevent.
# ---------------------------------------------------------------------------------------------

#: Bumped by an additive change to the layout.  Carried in `layout.json` AND in every
#: `key.json`, so a store written by one build is read by another without guessing.
LAYOUT_VERSION = 1

ROOT_MARKER = "layout.json"
CLIPS_DIRNAME = "clips"
PARTIAL_MARKER = ".partial"
MEDIA_NAME = "clip.mp4"
TRANSCRIPT_NAME = "transcript.json"
THUMB_NAME = "thumb.jpg"
KEY_NAME = "key.json"
KEY_TMP_NAME = "key.json.tmp"

#: 20261007T130648Z-0001 -- 8 date digits, `T`, 6 time digits, `Z`, `-`, >=4 seq digits.
#: The `Z` is literal and the digits are UTC: a clip_id is sortable by start time as text.
CLIP_ID_RE = re.compile(r"^(\d{8})T(\d{6})Z-(\d{4,})$")

#: The MEASURED capture rate of this box's 1080p60 clip, and its provenance.  It is not a
#: universal constant -- a different encoder or resolution moves it -- but it is the rate a
#: default budget on THIS machine is actually buying, and quoting a byte budget without
#: translating it into minutes is how a "generous" retention limit turns out to be 12 minutes.
#:   file      H:\sotto\_moved\aireplay\_main\_lane17-run\clip-speech.mp4
#:   size      98 099 914 B
#:   duration  16.733333 s   (ffprobe format=duration, rc=0, 2026-10-07)
#:   bit_rate  46 900 358 bit/s
MEASURED_BYTES_PER_SECOND = 98099914 / 16.733333


class LayoutError(Exception):
    """Any refusal in this module.  Raised, never returned as a sentinel."""


def _diag(errors: list[str] | None, message: str) -> None:
    """Record a filesystem failure the caller can ASSERT on.

    Nothing in this module swallows an `OSError` and then reports a byte count.  A file that
    cannot be stat'd is missing from the store's measured size, and a store whose size is
    quietly wrong evicts against a fiction -- so the failure is handed to the caller in a
    list and every gate arm asserts the list is empty.
    """
    print(f"CLIP_STORE_DIAG {message}", file=sys.stderr, flush=True)
    if errors is not None:
        errors.append(message)


# ---------------------------------------------------------------------------------------------
# clip_id <-> instant.  Pure, UTC, locale-free.
# ---------------------------------------------------------------------------------------------


def make_clip_id(started_at_s: float, seq: int) -> str:
    """`(epoch_seconds, seq)` -> `20261007T130648Z-0001`.

    The same inputs give the same id on every machine in every time zone: the stamp is
    `datetime.fromtimestamp(ts, tz=timezone.utc)`, so a host on UTC-03:00 files a clip under
    the UTC date, not its own.  Local-date filing is how a clip store ends up with two
    "yesterday" folders after a DST jump.
    """
    if not isinstance(started_at_s, (int, float)) or started_at_s != started_at_s:
        raise LayoutError(f"started_at_s must be a real number, got {started_at_s!r}")
    if int(seq) < 0:
        raise LayoutError(f"seq must be >= 0, got {seq!r}")
    stamp = datetime.fromtimestamp(float(started_at_s), tz=timezone.utc)
    return f"{stamp.strftime('%Y%m%dT%H%M%SZ')}-{int(seq):04d}"


@dataclass(frozen=True)
class ClipId:
    """The three facts a `clip_id` encodes.  Nothing else is derivable from the id."""

    clip_id: str
    started_at_s: float
    seq: int
    utc_date: str  # YYYY-MM-DD, the folder triple below `clips/`

    @property
    def date_parts(self) -> tuple[str, str, str]:
        y, m, d = self.utc_date.split("-")
        return y, m, d


def parse_clip_id(clip_id: str) -> ClipId:
    """`clip_id` -> its instants.  Raises `LayoutError` on anything that is not one of ours:
    an unrecognised directory is refused, never adopted."""
    m = CLIP_ID_RE.match(clip_id or "")
    if not m:
        raise LayoutError(f"not a clip id: {clip_id!r} (expected {CLIP_ID_RE.pattern})")
    date, clock, seq = m.groups()
    utc_date = f"{date[0:4]}-{date[4:6]}-{date[6:8]}"
    hh, mm, ss = int(clock[0:2]), int(clock[2:4]), int(clock[4:6])
    if hh > 23 or mm > 59 or ss > 59:
        raise LayoutError(f"clip id carries an impossible time: {clip_id!r}")
    # The regex admits `20261307T130648Z` (month 13), which `datetime` rejects with a bare
    # ValueError.  Converted, because this module's contract is that EVERY bad id arrives as
    # LayoutError: a caller catching LayoutError and a caller catching ValueError are two
    # different callers, and a crash is not a refusal.
    try:
        epoch = datetime(
            int(date[0:4]), int(date[4:6]), int(date[6:8]), hh, mm, ss, tzinfo=timezone.utc
        ).timestamp()
    except ValueError as exc:
        raise LayoutError(f"clip id carries an impossible date: {clip_id!r} ({exc})") from exc
    return ClipId(clip_id, float(epoch), int(seq), utc_date)


# ---------------------------------------------------------------------------------------------
# Paths.  Every one of these DERIVES from the clip_id by parsing it.  None of them takes a
# timestamp, so a path and an id can never disagree.
# ---------------------------------------------------------------------------------------------


def clip_dir(root: str | os.PathLike[str], clip_id: str) -> Path:
    """The one directory for `clip_id`: `root/clips/<YYYY>/<MM>/<DD>/<clip_id>` (UTC)."""
    parts = parse_clip_id(clip_id)
    y, m, d = parts.date_parts
    return Path(root) / CLIPS_DIRNAME / y / m / d / clip_id


def parse_clip_dir(path: str | os.PathLike[str]) -> ClipId:
    """The inverse of `clip_dir()`.  A reader holding only a path gets its instants back.

    This is the re-derivation half of the contract: the id and the folder triple under
    `clips/` are produced by DIFFERENT code, so a disagreement between them is detectable
    instead of invisible.
    """
    p = Path(path)
    parts = parse_clip_id(p.name)
    y, m, d = parts.date_parts
    # .../<clips>/<Y>/<M>/<D>/<clip_id>  -- four levels above the clip directory.
    up = [p.parent, p.parent.parent, p.parent.parent.parent, p.parent.parent.parent.parent]
    if up[3].name != CLIPS_DIRNAME:
        raise LayoutError(f"not a clip directory (no {CLIPS_DIRNAME!r} parent): {path}")
    if (up[0].name, up[1].name, up[2].name) != (d, m, y):
        raise LayoutError(
            f"clip {parts.clip_id} filed under {up[2].name}/{up[1].name}/{up[0].name}, "
            f"not under its own UTC date {parts.utc_date}"
        )
    return parts


def sidecars(cdir: str | os.PathLike[str]) -> dict[str, Path]:
    """The four named files of one clip directory.  Absent ones are simply absent on disk."""
    d = Path(cdir)
    return {
        "media": d / MEDIA_NAME,
        "transcript": d / TRANSCRIPT_NAME,
        "thumb": d / THUMB_NAME,
        "key": d / KEY_NAME,
    }


def clips_root(root: str | os.PathLike[str]) -> Path:
    return Path(root) / CLIPS_DIRNAME


def default_root() -> Path:
    """`%LOCALAPPDATA%\\Sotto\\clips`, the store a desktop app owns.  Never used by the gate:
    every arm is handed an explicit root so it cannot touch the owner's real library."""
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "Sotto" / "clips"


# ---------------------------------------------------------------------------------------------
# Iterating and measuring what is actually on disk.
# ---------------------------------------------------------------------------------------------


@dataclass
class ClipDir:
    """One directory found by `iter_clips()`, with the FACTS measured from the filesystem."""

    path: Path
    clip_id: str
    size_bytes: int          # measured by walking, not assumed from what the writer intended
    started_at_s: float | None
    has_partial: bool
    has_key: bool
    has_media: bool
    errors: tuple[str, ...] = ()


def iter_clips(root: str | os.PathLike[str], errors: list[str] | None = None) -> Iterator[ClipDir]:
    """Walk the store.  A directory whose name is not a clip id is skipped, not repaired."""
    base = clips_root(root)
    if not base.is_dir():
        return
    for ym in sorted(base.glob("*/*/*")):
        if not ym.is_dir():
            continue
        for cdir in sorted(p for p in ym.iterdir() if p.is_dir()):
            if not CLIP_ID_RE.match(cdir.name):
                continue  # a foreign directory: leave it alone
            sc = sidecars(cdir)
            local: list[str] = []
            size = 0
            for f in cdir.rglob("*"):
                if f.is_file():
                    try:
                        size += f.stat().st_size
                    except OSError as exc:
                        _diag(local, f"stat failed, size UNDERCOUNTED: {f}: {exc}")
            try:
                started = parse_clip_id(cdir.name).started_at_s
            except LayoutError as exc:
                started = None
                _diag(local, f"unparseable clip id {cdir.name!r}: {exc}")
            if errors is not None:
                errors.extend(local)
            yield ClipDir(
                path=cdir,
                clip_id=cdir.name,
                size_bytes=size,
                started_at_s=started,
                has_partial=(cdir / PARTIAL_MARKER).exists(),
                has_key=sc["key"].is_file(),
                has_media=sc["media"].is_file(),
                errors=tuple(local),
            )


def tree_bytes(root: str | os.PathLike[str], errors: list[str] | None = None) -> int:
    """The store's REAL size in bytes, measured by a full walk.  This is the number the
    budget is compared against -- never a sum of what a writer believed it wrote."""
    total = 0
    base = Path(root)
    if not base.exists():
        return 0
    for f in base.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError as exc:
                _diag(errors, f"stat failed, tree size UNDERCOUNTED: {f}: {exc}")
    return total


def volume_free_bytes(path: str | os.PathLike[str]) -> int:
    """Free space on the VOLUME holding `path`.  `shutil.disk_usage` on the store root, so the
    budget is compared with the disk the store is actually on."""
    usage = shutil.disk_usage(str(Path(path).resolve()))
    return int(usage.free)


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Whole-file SHA-256 -- the index's `content_key`.  Never sampled, never partial."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------
# THE READ RULES.  This table is the answer to "can the code that reads recover the layout".
# A reader must dispatch here on the version stamped in the file; an absent rule is a refusal,
# never a silent fallback to v1.  Adding a v2 means ADDING a rule and leaving v1 intact.
# ---------------------------------------------------------------------------------------------


def _read_v1(obj: dict[str, Any]) -> dict[str, Any]:
    """v1: flat.  `media`/`transcript`/`thumb` are names relative to the clip directory."""
    for required in ("clip_id", "media", "layout_version"):
        if required not in obj:
            raise LayoutError(f"v1 key is missing {required!r}")
    if int(obj["layout_version"]) != 1:
        raise LayoutError("v1 reader refuses a non-v1 key")
    return obj


READ_RULES: dict[int, Any] = {1: _read_v1}


def read_key(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read and version-dispatch one `key.json`.  An unknown/absent version is REFUSED."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise LayoutError(f"unreadable key {p}: {exc}") from exc
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LayoutError(f"key {p} is not JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise LayoutError(f"key {p} is not an object")
    if "layout_version" not in obj:
        raise LayoutError(f"key {p} carries no layout_version -- refused, not guessed")
    version = int(obj["layout_version"])
    rule = READ_RULES.get(version)
    if rule is None:
        raise LayoutError(
            f"key {p} is layout_version={version}; this build has NO read rule for it "
            f"(known: {sorted(READ_RULES)}). Refusing beats reading a v2 as v1."
        )
    return rule(obj)


def walk_keys(root: str | os.PathLike[str], errors: list[str] | None = None) -> list[dict[str, Any]]:
    """The index-key population, rebuilt from DISK ALONE -- no db, no in-memory state.

    This is what makes the store survivable: lose `store.db` and the index is reconstructible
    from these files, because every key is self-describing.  A key that exists but cannot be
    read is reported, not skipped: a clip the store cannot describe is one the index must not
    claim, and silence about it is how a library acquires invisible holes.
    """
    keys: list[dict[str, Any]] = []
    for c in iter_clips(root, errors=errors):
        if not c.has_key or c.has_partial:
            continue  # only COMMITTED dirs contribute an index key
        try:
            obj = read_key(sidecars(c.path)["key"])
        except LayoutError as exc:
            _diag(errors, f"committed dir has an unreadable key, OMITTED from the index: "
                          f"{c.clip_id}: {exc}")
            continue
        obj["_path"] = str(c.path)
        obj["_size_bytes_measured"] = c.size_bytes
        keys.append(obj)
    keys.sort(key=lambda k: k.get("clip_id", ""))
    return keys


# ---------------------------------------------------------------------------------------------
# Writing.  The `.partial` marker is the whole protocol.
# ---------------------------------------------------------------------------------------------


class ClipWriter:
    """Write one clip, in an order that cannot be observed half-done.

    The caller MUST call `commit()` or `abort()`.  Leaving the object open is exactly the
    crash this layout is built to survive, and a leftover `.partial` dir is a receipt of it.
    """

    def __init__(self, root: str | os.PathLike[str], clip_id: str) -> None:
        self.clip_id = clip_id
        self.path = clip_dir(root, clip_id)
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / PARTIAL_MARKER).write_bytes(b"")  # BEFORE any media byte
        self._committed = False

    def _write(self, name: str, data: bytes) -> Path:
        p = self.path / name
        with open(p, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())  # the bytes must be on disk before the marker moves
        return p

    def write_media(self, data: bytes) -> Path:
        return self._write(MEDIA_NAME, data)

    def write_transcript(self, obj: dict[str, Any] | list[Any]) -> Path:
        return self._write(TRANSCRIPT_NAME, json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8"))

    def write_thumb(self, data: bytes) -> Path:
        return self._write(THUMB_NAME, data)

    def commit(self, *, duration_ms: int = 0, source_device: str = "", mode: str = "",
               extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Publish the clip.  The index key is written LAST and atomically.

        Returns the committed key.  After this returns, `walk_keys()` sees the clip; before
        it returns, nothing in the store claims the clip exists.
        """
        media = self.path / MEDIA_NAME
        if not media.is_file():
            raise LayoutError(f"commit refused: no media in {self.path}")
        size = media.stat().st_size
        if size == 0:
            raise LayoutError(f"commit refused: zero-byte media in {self.path}")
        key: dict[str, Any] = {
            "layout_version": LAYOUT_VERSION,
            "clip_id": self.clip_id,
            "started_at_s": parse_clip_id(self.clip_id).started_at_s,
            "ended_at_s": datetime.now(tz=timezone.utc).timestamp(),
            "media": MEDIA_NAME,
            "transcript": TRANSCRIPT_NAME if (self.path / TRANSCRIPT_NAME).is_file() else None,
            "thumb": THUMB_NAME if (self.path / THUMB_NAME).is_file() else None,
            "size_bytes": size,
            "mtime_ns": media.stat().st_mtime_ns,
            "duration_ms": int(duration_ms),
            "source_device": source_device,
            "mode": mode,
            "content_key": sha256_file(media),   # the index's identity: never the path
            "committed_at_s": datetime.now(tz=timezone.utc).timestamp(),
        }
        if extra:
            key.update(extra)
        tmp = self.path / KEY_TMP_NAME
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(key, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path / KEY_NAME)  # THE atomic commit step
        try:
            (self.path / PARTIAL_MARKER).unlink()
        except OSError as exc:  # the dir is already committed; report, do not pretend
            raise LayoutError(
                f"clip {self.clip_id} is COMMITTED but its {PARTIAL_MARKER} marker survived "
                f"({exc}); reconciliation will finish this one"
            ) from exc
        self._committed = True
        return key

    def abort(self) -> None:
        """Give up on this clip and take its bytes with it.  Loud on purpose."""
        removed = remove_clip_dir(self.path)
        print(
            f"CLIP_STORE_ABORT clip_id={self.clip_id} bytes={removed} "
            f"reason=caller-aborted-partial",
            flush=True,
        )

    def __enter__(self) -> "ClipWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._committed and exc_type is not None:
            self.abort()
        elif not self._committed:
            raise LayoutError(
                f"clip {self.clip_id} left open (no commit, no abort); the .partial marker "
                f"in {self.path} is the crash receipt"
            )


def remove_clip_dir(path: str | os.PathLike[str]) -> int:
    """Delete a clip directory and report the bytes ACTUALLY freed.

    Each file's size is counted only after its own unlink succeeds, so a file the OS refused
    to delete is not reported as freed space -- an eviction that claims to have freed a file it
    kept is how a "we have room now" answer lies.  Every refusal is printed, loudly, and
    counted out of the total.
    """
    p = Path(path)
    if not p.exists():
        return 0
    freed = 0
    for f in sorted((x for x in p.rglob("*") if x.is_file()), key=lambda x: -len(x.parts)):
        try:
            size = f.stat().st_size
            f.unlink()
        except OSError as exc:
            print(
                f"CLIP_STORE_EVICT_FAILED path={f} reason={exc} -- these bytes were NOT freed",
                file=sys.stderr,
                flush=True,
            )
            continue
        freed += size
    for d in sorted((x for x in p.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)):
        try:
            d.rmdir()
        except OSError as exc:
            # Non-empty only if a file above refused to go; already reported per-file.
            print(f"CLIP_STORE_EVICT_FAILED rmdir={d} reason={exc}", file=sys.stderr, flush=True)
    try:
        p.rmdir()
    except OSError as exc:
        print(f"CLIP_STORE_EVICT_FAILED rmdir={p} reason={exc}", file=sys.stderr, flush=True)
    return freed


def ensure_root(root: str | os.PathLike[str]) -> Path:
    """Create the store root and stamp its version, refusing to write into a foreign store."""
    r = Path(root)
    r.mkdir(parents=True, exist_ok=True)
    (r / CLIPS_DIRNAME).mkdir(parents=True, exist_ok=True)
    marker = r / ROOT_MARKER
    if marker.is_file():
        try:
            obj = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LayoutError(f"{marker} exists and is unreadable: {exc}") from exc
        found = int(obj.get("layout_version", 0))
        if found != LAYOUT_VERSION:
            raise LayoutError(
                f"store {r} is layout_version={found}; this build is {LAYOUT_VERSION}. "
                f"Refusing to write into a store of another layout."
            )
    else:
        marker.write_text(
            json.dumps(
                {
                    "layout_version": LAYOUT_VERSION,
                    "clips_dirname": CLIPS_DIRNAME,
                    "media": MEDIA_NAME,
                    "transcript": TRANSCRIPT_NAME,
                    "thumb": THUMB_NAME,
                    "key": KEY_NAME,
                    "partial_marker": PARTIAL_MARKER,
                    "created_at_s": datetime.now(tz=timezone.utc).timestamp(),
                },
                indent=1,
            ),
            encoding="utf-8",
        )
    return r


# ---------------------------------------------------------------------------------------------
# Reconciliation vocabulary.  The on-disk truth is stated here; `retention.py` decides.
# ---------------------------------------------------------------------------------------------

VERDICT_COMMITTED = "committed"
VERDICT_FINISH = "partial-committed"       # crash between commit and marker removal
VERDICT_DISCARD = "partial-uncommitted"    # crash before the key landed -> media is unusable
VERDICT_ORPHAN_KEY = "orphan-key"          # no marker, no key -> nothing claims it, nothing has it
VERDICT_MISSING_MEDIA = "missing-media"    # key claims a clip whose media is gone

#: Every verdict `classify()` can return.  A gate arm asserts on this SET, so a new state
#: cannot appear without breaking the check that enumerates it.
VERDICTS = (
    VERDICT_COMMITTED,
    VERDICT_FINISH,
    VERDICT_DISCARD,
    VERDICT_ORPHAN_KEY,
    VERDICT_MISSING_MEDIA,
)


@dataclass
class Classification:
    verdict: str
    reason: str
    key: dict[str, Any] | None = None
    key_error: str | None = None
    size_bytes: int = 0


def classify(c: ClipDir) -> Classification:
    """Decide what one clip directory IS.  Pure with respect to the filesystem facts in `c`."""
    if c.has_partial:
        if c.has_key:
            return Classification(
                VERDICT_FINISH, "committed, marker not yet unlinked", size_bytes=c.size_bytes
            )
        return Classification(
            VERDICT_DISCARD,
            "marker present and no key: the mp4 was never finalised (no finished moov)",
            size_bytes=c.size_bytes,
        )
    if not c.has_key:
        return Classification(
            VERDICT_ORPHAN_KEY,
            "no marker and no key: a directory, not a clip",
            size_bytes=c.size_bytes,
        )
    if not c.has_media:
        return Classification(
            VERDICT_MISSING_MEDIA,
            "key names a media file that is not there",
            size_bytes=c.size_bytes,
        )
    try:
        key = read_key(sidecars(c.path)["key"])
    except LayoutError as exc:
        return Classification(
            VERDICT_DISCARD, f"key unreadable: {exc}", size_bytes=c.size_bytes, key_error=str(exc)
        )
    if key.get("clip_id") != c.clip_id:
        return Classification(
            VERDICT_DISCARD,
            f"key claims clip_id={key.get('clip_id')!r} inside a directory named {c.clip_id!r}",
            size_bytes=c.size_bytes,
        )
    return Classification(VERDICT_COMMITTED, "key + media, no marker", key=key, size_bytes=c.size_bytes)


# ---------------------------------------------------------------------------------------------
# Report plumbing, shared with `retention.py` so the gate reads ONE shape.
# ---------------------------------------------------------------------------------------------


@dataclass
class Report:
    arm: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def check(self, name: str, ok: bool, detail: str) -> bool:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    @property
    def ok(self) -> bool:
        return all(c["ok"] for c in self.checks)

    def as_dict(self) -> dict[str, Any]:
        failed = [c for c in self.checks if not c["ok"]]
        return {
            "arm": self.arm,
            "ok": self.ok,
            "n_checks": len(self.checks),
            "n_failed": len(failed),
            "checks": self.checks,
            "population": self.facts.get("population"),
            "window": self.facts.get("window"),
            "facts": self.facts,
        }


def emit(report: Report, json_path: str | None) -> None:
    text = json.dumps(report.as_dict(), ensure_ascii=False, indent=1, default=str)
    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(text, encoding="utf-8")
    n_bad = len([c for c in report.checks if not c["ok"]])
    for c in report.checks:
        print(f"  [{'ok  ' if c['ok'] else 'RED '}] {c['name']}: {c['detail']}", flush=True)
    print(
        f"ARM {report.arm} {'PASS' if report.ok else 'RED'}  "
        f"({len(report.checks) - n_bad}/{len(report.checks)} checks ok)",
        flush=True,
    )


# ---------------------------------------------------------------------------------------------
# `python -m storage.layout --selftest` -- ARM 0.
# ---------------------------------------------------------------------------------------------


def _host_utc_offset_min() -> int:
    """Minutes the HOST is off UTC.  Printed so a reader can see whether a TZ probe that
    depends on a non-zero offset was measuring anything."""
    return int(-time.timezone / 60)


def selftest(work: str) -> Report:
    """The layout contract, checked against a REAL tree under `work`.

    Nothing here is mocked: a real root, real files, real bytes on the filesystem.  What is
    checked is the CLAIM, not the code path -- determinism, inverse derivation, atomic
    commit, refusal of an unknown version, and index keys rebuildable from disk alone.
    """
    rep = Report("layout")
    root = Path(work) / "layout-root"
    if root.exists():
        shutil.rmtree(root)
    ensure_root(root)

    # --- determinism + inverse derivation -----------------------------------------------------
    # The instants are built from their date components, not from a hand-copied epoch: an
    # epoch constant pasted by hand is how a gate asserts a string the code never produced.
    fixed = datetime(2026, 10, 7, 13, 6, 48, tzinfo=timezone.utc).timestamp()
    cid = make_clip_id(fixed, 7)
    rep.check(
        "A1.clip-id-is-pure",
        cid == make_clip_id(fixed, 7) == "20261007T130648Z-0007",
        f"make_clip_id({fixed}, 7) -> {cid} (computed twice, identical)",
    )
    path = clip_dir(root, cid)
    back = parse_clip_dir(path)
    rep.check(
        "A2.path-derives-and-parses-back",
        back.clip_id == cid and str(path).endswith(r"clips\2026\10\07\20261007T130648Z-0007"),
        f"{path.name} -> clip_id={back.clip_id} started_at_s={back.started_at_s}",
    )

    # --- the TZ trap --------------------------------------------------------------------------
    # A local-date layout files this clip under the HOST's own date.  02:00Z is 23:00 of the
    # PREVIOUS day anywhere west of Greenwich, so this probe distinguishes the two rules
    # instead of agreeing with both.
    tz_probe = datetime(2026, 10, 7, 2, 0, 0, tzinfo=timezone.utc).timestamp()
    local_date = datetime.fromtimestamp(tz_probe).strftime("%Y-%m-%d")
    offset_min = _host_utc_offset_min()
    probe_distinguishes = offset_min != 0
    rep.check(
        "A3.filed-under-utc-not-local",
        parse_clip_dir(clip_dir(root, make_clip_id(tz_probe, 0))).utc_date == "2026-10-07"
        and local_date != "2026-10-07",
        f"instant 2026-10-07T02:00:00Z: clip id dates to UTC 2026-10-07, host local date for "
        f"the same instant is {local_date}, host UTC offset {offset_min} min"
        + ("" if probe_distinguishes else " -- host offset is 0, so this probe is VACUOUS"),
    )

    # --- a bad id is refused, not adopted ------------------------------------------------------
    refused = []
    for bad in ("not-an-id", "20261007T130648", "20261307T130648Z-0001", "20261007T996048Z-1"):
        try:
            parse_clip_id(bad)
            refused.append(f"{bad}=ACCEPTED")
        except LayoutError:
            refused.append(f"{bad}=refused")
    rep.check(
        "A4.bad-ids-refused",
        all("=refused" in r for r in refused),
        "; ".join(refused),
    )

    # --- writing N real clips, committing them -------------------------------------------------
    n_written = 0
    for i in range(6):
        w = ClipWriter(root, make_clip_id(fixed - i * 3600.0, i))
        w.write_media(b"\x00\x00\x00\x18ftypmp42" + bytes((i * 37 + k) % 251 for k in range(4096)))
        w.write_transcript({"segments": [{"start_ms": i * 1000, "text": f"clipe {i}"}]})
        w.write_thumb(bytes((k * 7) % 256 for k in range(256)))
        w.commit(duration_ms=1000 + i, mode="ring")
        n_written += 1
    rep.check("B1.committed-clips-landed", n_written == 6, f"{n_written} clips committed")

    # --- the commit is atomic and leaves nothing uncommitted ----------------------------------
    strays = [str(c.path) for c in iter_clips(root) if c.has_partial or not c.has_key]
    rep.check(
        "B2.no-partial-left-after-commit",
        not strays,
        f"{len(strays)} dir(s) carry a {PARTIAL_MARKER} marker or lack a key after commit"
        + (f": {strays[:3]}" if strays else ""),
    )

    # --- index keys rebuild from DISK ALONE ----------------------------------------------------
    errs: list[str] = []
    keys = walk_keys(root, errors=errs)
    rep.check(
        "B3.keys-rebuild-from-disk-alone",
        len(keys) == n_written
        and all(k.get("content_key") and k.get("size_bytes") for k in keys)
        and not errs,
        f"walk_keys() returned {len(keys)} key(s) with no db and no in-memory state; "
        f"content_key+size_bytes present on {sum(1 for k in keys if k.get('content_key'))}"
        f"/{len(keys)}; filesystem errors={len(errs)}",
    )

    # --- a store whose db is lost is still describable ----------------------------------------
    rep.check(
        "B4.keys-name-their-own-media",
        all((Path(k["_path"]) / k["media"]).is_file() for k in keys),
        f"{sum(1 for k in keys if (Path(k['_path']) / k['media']).is_file())}/{len(keys)} "
        f"keys point at a media file that exists",
    )

    # --- an UNKNOWN layout version is refused, never read as v1 --------------------------------
    unknown_dir = clip_dir(root, "20260101T000000Z-0001")
    unknown_dir.mkdir(parents=True, exist_ok=True)
    (unknown_dir / MEDIA_NAME).write_bytes(b"fake")
    (unknown_dir / KEY_NAME).write_text(
        json.dumps({"layout_version": 99, "clip_id": "20260101T000000Z-0001", "media": MEDIA_NAME}),
        encoding="utf-8",
    )
    try:
        read_key(unknown_dir / KEY_NAME)
        unknown_ok, unknown_detail = False, "a layout_version=99 key was ACCEPTED"
    except LayoutError as exc:
        unknown_ok, unknown_detail = True, f"refused: {exc}"
    rep.check("C1.unknown-layout-version-refused", unknown_ok, unknown_detail)

    # --- the classify vocabulary is total over the states it can be in ------------------------
    errs2: list[str] = []
    seen: dict[str, int] = {}
    for c in iter_clips(root, errors=errs2):
        v = classify(c).verdict
        seen[v] = seen.get(v, 0) + 1
    unknown_verdict = sorted(set(seen) - set(VERDICTS))
    rep.check(
        "C2.verdicts-are-from-the-declared-set",
        not unknown_verdict and not errs2,
        f"verdicts observed over {sum(seen.values())} dir(s): {sorted(seen)}; "
        f"declared set: {list(VERDICTS)}; undeclared: {unknown_verdict}; "
        f"filesystem errors={len(errs2)}",
    )

    rep.facts["population"] = {
        "root": str(root),
        "clips_committed": len(keys),
        "dirs_total": sum(seen.values()),
        "bytes_measured": tree_bytes(root),
        "host_utc_offset_min": offset_min,
        "tz_probe_vacuous": not probe_distinguishes,
    }
    rep.facts["window"] = {
        "oldest_clip_id": keys[0]["clip_id"] if keys else None,
        "newest_clip_id": keys[-1]["clip_id"] if keys else None,
        "span_s": (keys[-1]["started_at_s"] - keys[0]["started_at_s"]) if len(keys) > 1 else 0.0,
        "note": "UTC, derived from clip_id only",
    }
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m storage.layout")
    ap.add_argument("--selftest", action="store_true", help="run ARM 0 and exit with its rc")
    ap.add_argument("--work", default="_main/_lane22-run/layout-selftest")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    if not args.selftest:
        ap.error("nothing to do: pass --selftest (or use `storage.retention --arm X`)")
    rep = selftest(args.work)
    emit(rep, args.json)
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())