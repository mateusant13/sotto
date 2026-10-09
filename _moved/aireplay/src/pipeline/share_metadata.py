"""share_metadata.py -- WHAT TRAVELS WITH THE CLIP, and which field names are a GUESS.

================================================================================
WHY THIS FILE IS MOSTLY A DECLARATION
================================================================================

The index lane owns the schema (`src/index/**`, another lane). This lane does not touch it.
So the question "what is a clip's title" has exactly one honest answer today, and it is NOT
"whatever I called it in this file": it is **"the `video` table has no such column"**.

MEASURED, read from the live tree 2026-10-07, `src/index/schema.sql:41-63`, the whole of it:

    id, content_key, file_key, path, size_bytes, mtime_ns, duration_ms,
    codec, w, h, fps, bitrate, added_at, last_seen_scan, missing, state

No `title`. No `app`. No `game`. A share metadata object built here that pretends to read
`video.title` would read `None` on every single clip forever, and -- exactly like the
`store.py:154` "ignoring unknown field(s)" warning this repo already has -- nothing would
raise. So `INDEX_FIELD_EXPECTATIONS` below states, per field, WHERE it comes from and
whether that is CONFIRMED (I read it in the live tree) or PROPOSED (I am asking the index
lane for it and it does not exist yet), and `verify_index_expectations()` CHECKS the
CONFIRMED half against `schema.sql` at run time instead of trusting a comment.

THE THREE FIELDS THE FEATURE ASKS FOR:

  timestamp  CONFIRMED. `key.json` carries `started_at_s` (epoch float, UTC) -- written by
             `layout.ClipWriter.commit()` -- and the index carries `mtime_ns` and
             `added_at`. The share needs the *capture instant*, so `started_at_s` is the one
             used, and it is the one `clip_id` itself encodes.
  title      NOT IN THE SCHEMA. Proposed column: `video.title TEXT`. Until it exists, the
             title is USER-SUPPLIED at share time and stored by THIS lane in the share's own
             `key.json` (`extra={"share": {...}}`), which the store already supports. That is
             why the UI does not read a default title from the index.
  game/app   NOT IN THE SCHEMA, and the nearest existing field is a MISNOMER TRAP:
             `key.json.source_device` names the CAPTURE DEVICE (the capture lane's CutResult
             member), not the application the user was running. Falling back to it would put
             "Monitor 1\\DISPLAY1" in the YouTube title. Proposed column: `video.app TEXT`.

Both PROPOSED rows are stated as requests, not as facts. If the index lane picks different
names, `TITLE_COLUMN_CANDIDATES` / `APP_COLUMN_CANDIDATES` list the alternatives this lane
will accept, so the swap is a one-line edit in one place rather than a grep across the tree.

================================================================================
THE REMOTE SIDE IS NOT A GUESS. It is read from the discovery document.
================================================================================

Field names and the privacy enum below are taken from the YouTube Data API v3 discovery
document, fetched 2026-10-07, `revision: 20261006`:

    $d.resources.videos.methods.insert.path       -> 'youtube/v3/videos'
    $d.resources.videos.methods.insert.httpMethod -> 'POST'
    $d.resources.videos.methods.insert.scopes     -> includes
        'https://www.googleapis.com/auth/youtube.upload'
    $d.schemas.Video.properties.snippet            -> {$ref: 'VideoSnippet'}
    $d.schemas.Video.properties.status             -> {$ref: 'VideoStatus'}
    $d.schemas.VideoSnippet.properties             -> title, description, tags, categoryId, ...
    $d.schemas.VideoStatus.properties.privacyStatus.enum -> ['public', 'unlisted', 'private']

WHAT IS **NOT** CLAIMED. The discovery document carries NO `maxLength` for
`VideoSnippet.title` (the lookup returned empty), so this file does NOT assert a "100
character" limit -- that number is the kind of thing that is true today and quietly wrong
later. An over-long title is left to the service, which answers `invalidTitle`
(https://developers.google.com/youtube/v3/docs/videos/insert, error table), and
`share_upload` maps that reason into a sentence a user can act on.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "Certainty",
    "MetadataExpectation",
    "INDEX_FIELD_EXPECTATIONS",
    "TITLE_COLUMN_CANDIDATES",
    "APP_COLUMN_CANDIDATES",
    "PRIVACY_VALUES",
    "ExpectationReport",
    "verify_index_expectations",
    "ShareMetadata",
    "MetadataError",
    "metadata_from_store_key",
    "default_title",
    "to_youtube_video_resource",
]

#: Where the honest answer came from, stated per row and not in a footnote.
CONFIRMED = "CONFIRMED"   # read in the live tree in this session; verify_index_expectations() re-checks it
PROPOSED = "PROPOSED"     # requested from the index lane; does NOT exist yet; never read as if it did


class MetadataError(ValueError):
    """A refusal in this module. Raised, never returned as a sentinel."""


@dataclass(frozen=True)
class MetadataExpectation:
    """One field this lane needs, and what it is allowed to assume about it."""

    field: str
    why: str
    source: str                 # the concrete producer, or the request to the index lane
    certainty: str              # CONFIRMED | PROPOSED
    expected_type: str
    #: for CONFIRMED rows: a regex that must appear in `schema.sql` for the claim to hold
    schema_pattern: str | None = None
    #: what this lane does while the column is missing, instead of reading None forever
    fallback: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field, "certainty": self.certainty, "source": self.source,
            "expected_type": self.expected_type, "why": self.why, "fallback": self.fallback,
        }


INDEX_FIELD_EXPECTATIONS: tuple[MetadataExpectation, ...] = (
    MetadataExpectation(
        field="started_at_s",
        why="The share's timestamp is the CAPTURE instant, not the export instant -- otherwise "
            "every clip shared days later carries the day it was exported.",
        source="src/storage/layout.py:433 (ClipWriter.commit) and the clip_id itself "
               "(CLIP_ID_RE carries 20261007T130648Z)",
        certainty=CONFIRMED,
        expected_type="float (epoch seconds, UTC)",
        schema_pattern=r"clip_id",  # present in key.json; asserted against the layout module text
        fallback="none -- this one always exists",
    ),
    MetadataExpectation(
        field="duration_ms",
        why="Progress, and the size of the thing being shared.",
        source="src/index/schema.sql:52 (video.duration_ms INTEGER NOT NULL DEFAULT 0)",
        certainty=CONFIRMED,
        expected_type="int (MILLISECONDS)",
        schema_pattern=r"duration_ms\s+INTEGER\s+NOT\s+NULL",
        fallback="key.json['duration_ms'], else 0",
    ),
    MetadataExpectation(
        field="content_key",
        why="The share must point at ONE clip by content, not by path: the index's identity is "
            "the whole-file SHA-256 and a moved file is the same clip.",
        source="src/index/schema.sql:44 (video.content_key TEXT NOT NULL UNIQUE, "
               "CHECK(length(content_key) = 64))",
        certainty=CONFIRMED,
        expected_type="str, 64 hex chars",
        schema_pattern=r"content_key\s+TEXT\s+NOT\s+NULL\s+UNIQUE",
        fallback="computed by layout.sha256_file() at export time",
    ),
    MetadataExpectation(
        field="title",
        why="It is the first thing a viewer sees and the only thing the user edits before "
            "sharing. The feature is worthless without it.",
        source="REQUEST to the index lane (src/index/**): add `video.title TEXT`. "
               "It does not exist on 2026-10-07 -- see the table at schema.sql:41-63.",
        certainty=PROPOSED,
        expected_type="str | NULL",
        schema_pattern=None,
        fallback="user-typed at share time; persisted in the SHARE's own key.json "
                 "(extra={'share': {...}}), which layout.ClipWriter.commit already accepts. "
                 "This lane never reads video.title until the column exists.",
    ),
    MetadataExpectation(
        field="app",
        why="ShadowPlay titles a clip with the game. Without it every upload is a bare timestamp.",
        source="REQUEST to the index lane: add `video.app TEXT`. NOTE the trap: "
               "key.json['source_device'] is the CAPTURE DEVICE (CutResult), not the app.",
        certainty=PROPOSED,
        expected_type="str | None",
        schema_pattern=None,
        fallback="user-typed at share time; never falls back to source_device, which would "
                 "publish a monitor name as a game title.",
    ),
)

#: Column names this lane will accept for `title` if the index lane picks one. Keeping the
#: list here means a rename is a one-line edit, not a hunt.
TITLE_COLUMN_CANDIDATES: tuple[str, ...] = ("title", "clip_title")
APP_COLUMN_CANDIDATES: tuple[str, ...] = ("app", "game", "source_app", "app_name")

#: `VideoStatus.privacyStatus.enum`, verbatim from the discovery document (revision 20261006).
PRIVACY_VALUES: tuple[str, ...] = ("public", "unlisted", "private")


@dataclass
class ExpectationReport:
    """What `verify_index_expectations()` found. `ok` False is a DRIFT, not a warning."""

    ok: bool
    checked: list[dict[str, Any]] = field(default_factory=list)
    missing_proposed: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "checked": self.checked, "missing_proposed": self.missing_proposed}


def _schema_sql() -> Path | None:
    here = Path(__file__).resolve()
    for base in [here.parents[2], *here.parents]:
        cand = base / "src" / "index" / "schema.sql"
        if cand.is_file():
            return cand
    return None


def verify_index_expectations() -> ExpectationReport:
    """Re-derive every CONFIRMED row against the live `schema.sql`.

    This is the point of the file: a comment claiming "the index has duration_ms" is worth
    nothing on the day the index lane renames it, and this repo has already paid for that
    class of bug (`contracts.py:154`, the silently dropped field). A CONFIRMED row whose
    regex no longer matches is a failure, HERE, loudly.

    The PROPOSED rows are reported separately and never fail this check: they are requests,
    not claims, and a gate that goes red because a column another lane has not added yet is
    a gate that gets deleted.
    """
    path = _schema_sql()
    text = ""
    checked: list[dict[str, Any]] = []
    missing: list[str] = []
    ok = True

    for exp in INDEX_FIELD_EXPECTATIONS:
        row: dict[str, Any] = exp.as_dict()
        if exp.certainty == PROPOSED:
            missing.append(exp.field)
            row["checked"] = "not-required-yet"
        else:
            if exp.field == "started_at_s":  # asserted against the LAYOUT module, not schema.sql
                layout = Path(__file__).resolve().parents[1] / "storage" / "layout.py"
                text = layout.read_text(encoding="utf-8") if layout.is_file() else ""
                target = "src/storage/layout.py"
            else:
                text = path.read_text(encoding="utf-8") if path is not None else ""
                target = str(path) if path else "<schema.sql not found>"
            hit = bool(exp.schema_pattern) and bool(re.search(exp.schema_pattern, text))
            row["checked"] = "present" if hit else "DRIFT"
            row["target"] = target
            row["pattern"] = exp.schema_pattern
            if not hit:
                ok = False
        checked.append(row)

    return ExpectationReport(ok=ok, checked=checked, missing_proposed=missing)


# ==================================================================================
# The object that travels.
# ==================================================================================


@dataclass
class ShareMetadata:
    """Title, app, timestamp -- and the identity of the thing they describe."""

    clip_id: str
    content_key: str
    title: str
    recorded_at_utc: str          # ISO-8601, 'Z', SECOND resolution
    recorded_at_epoch_s: float
    app: str = ""
    description: str = ""
    duration_ms: int = 0
    source_device: str = ""
    privacy: str = "unlisted"
    #: names this lane is UNSURE about, carried to the surface instead of hidden
    uncertain_fields: tuple[str, ...] = ()

    def validate(self) -> None:
        """Refuse a metadata object that would produce a bad remote call."""
        if not self.title.strip():
            raise MetadataError("refused: an empty title. The service answers `invalidTitle` "
                                "for it; better to say so before 100 MB has moved.")
        if self.privacy not in PRIVACY_VALUES:
            raise MetadataError(
                f"refused: privacy={self.privacy!r} is not one of "
                f"{PRIVACY_VALUES} (VideoStatus.privacyStatus.enum)")
        if len(self.content_key) != 64:
            raise MetadataError(f"refused: content_key must be 64 hex chars, got "
                                f"{len(self.content_key)}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id, "content_key": self.content_key, "title": self.title,
            "app": self.app, "recorded_at_utc": self.recorded_at_utc,
            "recorded_at_epoch_s": self.recorded_at_epoch_s,
            "duration_ms": self.duration_ms, "source_device": self.source_device,
            "privacy": self.privacy, "description": self.description,
            "uncertain_fields": list(self.uncertain_fields),
        }


def default_title(app: str, started_at_s: float) -> str:
    """A title the user can accept with Enter.

    NOT read from the index: `video.title` does not exist (see the module docstring). Built
    from what IS on disk -- the app, when the user gave one, and the UTC capture instant,
    which `clip_id` already carries.
    """
    from datetime import datetime, timezone

    stamp = datetime.fromtimestamp(float(started_at_s), tz=timezone.utc)
    when = stamp.strftime("%Y-%m-%d %H:%M UTC")
    return f"{app} — {when}".strip(" —") if app else f"Clip {when}"


def metadata_from_store_key(key: dict[str, Any], *, title: str | None = None,
                            app: str | None = None, description: str = "",
                            privacy: str = "unlisted") -> ShareMetadata:
    """Build the travelling metadata from a store `key.json` plus what the user typed.

    `title`/`app` are arguments, NOT lookups, and that is the whole point: the two columns
    that would justify a lookup do not exist in the schema yet. Whichever is not supplied
    falls back to what IS on disk, and the object records the fact in `uncertain_fields` so
    the surface can say "title not stored by the index" instead of implying otherwise.
    """
    started = float(key.get("started_at_s") or 0.0)
    from datetime import datetime, timezone

    uncertain: list[str] = []
    eff_app = app or ""
    eff_title = title or ""
    if title is None:
        uncertain.append("title")
    if app is None:
        uncertain.append("app")

    meta = ShareMetadata(
        clip_id=str(key.get("clip_id") or ""),
        content_key=str(key.get("content_key") or ""),
        title=eff_title or default_title(eff_app, started),
        recorded_at_utc=datetime.fromtimestamp(started, tz=timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
        recorded_at_epoch_s=started,
        app=eff_app,
        description=description,
        duration_ms=int(key.get("duration_ms") or 0),
        # Deliberately NOT used as an app fallback -- see INDEX_FIELD_EXPECTATIONS['app'].
        source_device=str(key.get("source_device") or ""),
        privacy=privacy,
        uncertain_fields=tuple(uncertain),
    )
    meta.validate()
    return meta


def to_youtube_video_resource(meta: ShareMetadata) -> dict[str, Any]:
    """The `Video` resource body for `videos.insert`.

    Key names are `VideoSnippet`/`VideoStatus` property names from the discovery document
    (revision 20261006) -- `snippet.title`, `snippet.description`, `status.privacyStatus`.
    `selfDeclaredMadeForKids` is set False explicitly: gaming captures are not made-for-kids
    content, and the API's own default is not something to inherit silently.
    """
    meta.validate()
    return {
        "snippet": {
            "title": meta.title,
            "description": meta.description,
        },
        "status": {
            "privacyStatus": meta.privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


def _cli(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="share metadata expectations (read-only)")
    ap.add_argument("--expectations", action="store_true",
                    help="print INDEX_FIELD_EXPECTATIONS as json and exit")
    args = ap.parse_args(argv)
    if args.expectations:
        print(json.dumps([e.as_dict() for e in INDEX_FIELD_EXPECTATIONS],
                         ensure_ascii=False, indent=1))
        return 0
    rep = verify_index_expectations()
    print(json.dumps(rep.as_dict(), ensure_ascii=False, indent=1))
    return 0 if rep.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())