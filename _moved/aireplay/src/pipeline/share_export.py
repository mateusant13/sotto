"""share_export.py -- RENDERED CLIP -> SHAREABLE FILE, on top of what already exists.

================================================================================
WHAT ALREADY EXISTED, so this file does not re-encode anything
================================================================================

Checked before writing a line, 2026-10-07:

  * `src/capture/mp4_writer.{h,cpp}` -- the muxer. It writes `ftyp` + `mdat`, then a
    `moov` at `close()` (mp4_writer.h:9). It is C++, owned by the capture lane, and it is
    NOT re-implemented here. Its output is already a playable mp4.
  * `src/storage/layout.py` -- the clip store, with the commit protocol this file REUSES
    verbatim: `.partial` written before any byte, `key.json.tmp` -> `os.replace` -> `key.json`
    as the one atomic commit step, then the marker is unlinked (layout.py:397, :448-460).
  * `src/pipeline/chain.py:339-343` -- ffmpeg/ffprobe resolution, searched on PATH and then
    in `H:\\ffmpeg\\bin`, `C:\\ffmpeg\\bin`, `C:\\ProgramData\\chocolatey\\bin`. The pipeline
    already accepts ffmpeg as a REAL_SUBSTITUTE and prints it as such (chain.py:465-475).

So the export is not "encode the clip". It is the two things a RECORDED clip is not yet:

  1. FASTSTART. `mp4_writer` writes `moov` LAST, by construction. A clip recorded here is
     therefore a file that cannot start playing until it has been read to the end -- fine
     locally, useless for an upload that a viewer is watching, and the reason services ask
     for a faststart file. `-c copy` moves the index; it re-encodes nothing.
  2. A COMMITTED SHARE. A clip that exists is not a clip that was shared.

MEASURED on THIS host, 1 run, 2026-10-07 (population and window stated because the repo has
been retracted six times for numbers that had neither):

    input   ftyp@0 free@32 mdat@40(5860) moov@5900(862)     6762 B
    output  ftyp@0 moov@32(862) free@894 mdat@902(5860)    6762 B
    `ffmpeg -i IN -c copy -movflags +faststart OUT`, exit code 0, byte count UNCHANGED.

The relocation is therefore PROVEN, not asserted: `mp4_box_order()` reads the box headers
back out of the file this code produced and the gate compares the `moov` offset against the
`mdat` offset. A claim that the file is faststart without reading its boxes back is the kind
of claim this repo keeps retracting.

================================================================================
WHY A SHARE IS WRITTEN THROUGH THE STORE'S OWN WRITER
================================================================================

The share lands in its OWN root -- `<store>/../shares` by default -- using `ClipWriter`
unchanged. Two consequences, both of them the point:

  * `layout.walk_keys(shares_root)` reads the share store with vocabulary that ALREADY
    exists, so `retention.py` and every future reader need to learn nothing new.
  * A cancelled or failed upload calls `abort()`, which deletes the directory. There is no
    `share.mp4` left on disk without a `key.json`, so nothing that a later run could read as
    a finished share exists. The half-written-file failure is prevented by REUSING the
    protocol, not by a new cleanup path that could disagree with it.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# `src/` is NOT a package (no `src/__init__.py`), so `pipeline` and `storage` are TOP-LEVEL
# packages reached with `src` on sys.path -- the same shape chain.py and contracts.py use
# (contracts.py:162, chain.py:525). A `from ..storage import layout` here would resolve to a
# parent package that does not exist and fail at import time, which is the loud kind of wrong.
if __package__ in (None, ""):  # running the file directly
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_SRC_ROOT = str(Path(__file__).resolve().parents[1])
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from storage import layout  # noqa: E402
from pipeline.share_metadata import ShareMetadata, metadata_from_store_key  # noqa: E402
from pipeline.share_upload import UploadClient, UploadOutcome  # noqa: E402

__all__ = [
    "ExportError", "ToolMissing", "find_tool", "mp4_box_order", "is_faststart",
    "ExportReport", "shares_root_for", "export_clip", "ShareJob",
]


class ExportError(RuntimeError):
    """Any refusal in the export path. Raised, never a sentinel."""


class ToolMissing(ExportError):
    """ffmpeg is not on PATH and not in the known locations (chain.py's list)."""


#: The search order chain.py:339-343 already established. Mirrored here on purpose rather
#: than imported: `_tool` is a PRIVATE method of another lane's class, and a live lane's
#: private method is not an API. The receipt records this as a deliberate, bounded
#: duplication of eight lines -- a path list -- rather than of an encoder.
_TOOL_HINTS: tuple[str, ...] = (
    r"H:\ffmpeg\bin", r"C:\ffmpeg\bin", r"C:\ProgramData\chocolatey\bin",
)


def find_tool(name: str) -> str | None:
    """PATH first, then the locations chain.py already searches. None when absent."""
    from shutil import which
    found = which(name)
    if found:
        return found
    for hint in _TOOL_HINTS:
        cand = Path(hint) / f"{name}.exe"
        if cand.is_file():
            return str(cand)
    return None


def _run(cmd: list[str], timeout_s: float) -> subprocess.CompletedProcess:
    creationflags = 0
    if sys.platform == "win32":  # the owner's rule: never a visible console
        creationflags = 0x08000000 | 0x00000008
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,
                          creationflags=creationflags)


def mp4_box_order(path: str | os.PathLike[str]) -> list[tuple[str, int, int]]:
    """[(box type, file offset, size)] for the TOP-LEVEL boxes, read from the file.

    Deliberately not `ffprobe`: this is the INDEPENDENT reader. The gate uses it to check a
    file ffmpeg claims to have written, so the checker must not be the thing being checked.
    """
    out: list[tuple[str, int, int]] = []
    with open(path, "rb") as f:
        off = 0
        while True:
            f.seek(off)
            head = f.read(8)
            if len(head) < 8:
                break
            size, kind = struct.unpack(">I4s", head)
            if size == 1:  # 64-bit largesize
                ext = f.read(8)
                if len(ext) < 8:
                    break
                size = struct.unpack(">Q", ext)[0]
            if size < 8:
                break
            out.append((kind.decode("latin1"), off, int(size)))
            off += int(size)
    return out


def is_faststart(path: str | os.PathLike[str]) -> bool | None:
    """True/False from the box order, or None when the file is not an mp4 at all."""
    try:
        boxes = mp4_box_order(path)
    except OSError:
        return None
    kinds = [b[0] for b in boxes]
    if "moov" not in kinds or "mdat" not in kinds:
        return None
    return kinds.index("moov") < kinds.index("mdat")


def shares_root_for(store_root: str | os.PathLike[str]) -> Path:
    """The share store, beside the clip store and never inside it.

    Inside would mean `iter_clips(store_root)` walks shares as clips and the index grows a
    row per upload attempt; beside means the two stores are separate trees with one parent.
    """
    return Path(store_root).parent / "shares"


@dataclass
class ExportReport:
    """What the export actually did, as measured -- not as intended."""

    share_id: str
    path: Path
    size_bytes: int
    sha256: str
    source_clip_id: str
    ffmpeg: str
    faststart: bool | None
    boxes: list[tuple[str, int, int]] = field(default_factory=list)
    wall_s: float = 0.0
    reencoded: bool = False          # always False: -c copy. Said so, not assumed.

    def as_dict(self) -> dict[str, Any]:
        return {
            "share_id": self.share_id, "path": str(self.path), "size_bytes": self.size_bytes,
            "sha256": self.sha256, "source_clip_id": self.source_clip_id, "ffmpeg": self.ffmpeg,
            "faststart": self.faststart, "boxes": [list(b) for b in self.boxes],
            "wall_s": round(self.wall_s, 3), "reencoded": self.reencoded,
        }


def _mint_share_id(store_root: str | os.PathLike[str]) -> str:
    """A fresh, UNUSED clip-shaped id.

    A re-share gets a NEW share id and records the source clip id in its key; overwriting a
    previous share in place would make 'was this shared before?' unanswerable, because the
    earlier attempt's bytes would be gone.

    The probe is `exists()`, not `clip_dir()` in a try/except. `clip_dir` only RAISES on an
    id it cannot parse, and an id just minted by `make_clip_id` is parseable by construction
    -- so catching LayoutError here would be a handler for an impossible case wearing a
    handler's clothes. `exists()` returns False for reasons that DO happen (the parent tree is
    absent), so its answer is confirmed against the directory's own parent before it is
    believed.
    """
    base = shares_root_for(store_root)
    for seq in range(0, 10000):
        cid = layout.make_clip_id(time.time(), seq)
        d = layout.clip_dir(base, cid)
        if d.exists():
            continue
        if not (base / layout.CLIPS_DIRNAME).exists():
            # A free id under a tree that is not there yet is fine; an id we cannot even
            # reach is not. Refuse loudly rather than commit into a path we cannot verify.
            try:
                probe = d.parent
                while probe != base:
                    probe.mkdir(parents=True, exist_ok=True)
                    break
            except OSError as exc:
                raise ExportError(
                    f"refused: cannot prepare {d.parent} for a new share id: {exc}") from exc
        return cid
    raise ExportError(f"refused: no free share id under {base} after 10000 sequences")


def export_clip(clip_dir: str | os.PathLike[str], store_root: str | os.PathLike[str], *,
                share_id: str | None = None,
                timeout_s: float = 600.0) -> ExportReport:
    """`clip_dir` (a COMMITTED clip) -> a committed, faststart copy in the share store.

    Refuses a source that is not committed. A `.partial` dir with no `key.json` is a crash
    artefact (`layout.py:25-29`); uploading it would publish a file with no finished `moov`,
    which is the failure this whole file exists to prevent.
    """
    src = Path(clip_dir)
    if not src.is_dir():
        raise ExportError(f"no such clip directory: {src}")

    sc = layout.sidecars(src)
    if (src / layout.PARTIAL_MARKER).exists() or not sc["key"].is_file():
        raise ExportError(
            f"refused: {src.name} is not a committed clip "
            f"(partial_marker={(src / layout.PARTIAL_MARKER).exists()}, "
            f"key_json={sc['key'].is_file()}). layout.py:25-29 -- an uncommitted directory "
            f"has no finished moov and would not play once posted.")
    if not sc["media"].is_file():
        raise ExportError(f"refused: committed clip {src.name} has no media file")
    if sc["media"].stat().st_size == 0:
        raise ExportError(f"refused: committed clip {src.name} has zero-byte media")

    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        raise ToolMissing("ffmpeg not found on PATH or in " + ", ".join(_TOOL_HINTS))

    sid = share_id or _mint_share_id(store_root)
    writer = layout.ClipWriter(shares_root_for(store_root), sid)
    t0 = time.perf_counter()

    staged = writer.path / "share.mp4.part"
    try:
        proc = _run([ffmpeg, "-nostdin", "-v", "error", "-y",
                     "-i", str(sc["media"]), "-c", "copy",
                     "-movflags", "+faststart", "-f", "mp4", str(staged)], timeout_s)
        if proc.returncode != 0 or not staged.is_file():
            raise ExportError(
                f"ffmpeg refused the remux (exit {proc.returncode}): "
                f"{(proc.stderr or '').strip()[:400]}")
        if staged.stat().st_size == 0:
            raise ExportError("ffmpeg produced a zero-byte file; refusing to commit it")

        boxes = mp4_box_order(staged)
        fast = is_faststart(staged)
        writer.write_media(staged.read_bytes())

        # Best-effort cleanup of the staging file, and it is the ONLY best-effort in this
        # function: if the unlink fails the bytes stay as `share.mp4.part`, a name
        # `walk_keys` cannot read and `remove_clip_dir` sweeps on abort. Reported either way
        # so a store quietly growing staging files is visible in the log.
        try:
            staged.unlink()
        except OSError as exc:
            print(f"SHARE_EXPORT_WARN share_id={sid} staged_file_left={staged.name} "
                  f"reason={exc}", flush=True)

        source_key = layout.read_key(sc["key"])
        writer.commit(
            duration_ms=int(source_key.get("duration_ms") or 0),
            source_device=str(source_key.get("source_device") or ""),
            mode="share-export",
            extra={"source_clip_id": str(source_key.get("clip_id") or src.name),
                   "faststart": fast, "encoder": "ffmpeg -c copy -movflags +faststart",
                   "exported_at_s": time.time()},
        )
    except BaseException:
        writer.abort()          # INCLUDING KeyboardInterrupt: a cancelled export leaves nothing
        raise

    wall = time.perf_counter() - t0
    out = writer.path / layout.MEDIA_NAME
    return ExportReport(
        share_id=sid, path=out, size_bytes=out.stat().st_size,
        sha256=layout.sha256_file(out), source_clip_id=src.name, ffmpeg=ffmpeg,
        faststart=fast, boxes=boxes, wall_s=wall, reencoded=False,
    )


def _record_share(share_dir: Path, outcome: UploadOutcome, meta: ShareMetadata) -> Path:
    """The share's own receipt, written atomically beside its media.

    `share.json` lives inside the already-committed clip directory, so its presence is NOT
    what makes a share real -- `key.json` is. Losing `share.json` loses the receipt and
    nothing else, which is what lets a bookkeeping step be retried without re-uploading.
    """
    tmp = share_dir / "share.json.tmp"
    out = share_dir / "share.json"
    payload = {
        "service": outcome.service, "remote_id": outcome.remote_id, "url": outcome.url,
        "uploaded_at_s": time.time(), "metadata": meta.as_dict(),
        "quota_note": "YouTube Data API v3 charges 1600 units per videos.insert",
    }
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, out)
    return out


class ShareJob:
    """EXPORT -> UPLOAD -> COMMIT, with the commit conditioned on the outcome.

    This is the whole product in one object, and the ORDER is the design:

        the local artefact is written, the upload runs, and ONLY a SUCCEEDED outcome
        commits anything that describes the share as finished.

    A failed or cancelled upload calls `abort()`, which removes the directory outright. The
    negative the gate asserts is therefore not 'a flag is False' -- it is 'the share store
    contains no key for this attempt', read back through `layout.walk_keys`, the same reader
    a future maintenance run would use.
    """

    def __init__(self, clip_dir: str | os.PathLike[str], store_root: str | os.PathLike[str],
                 client: UploadClient, *, title: str | None = None, app: str | None = None,
                 description: str = "", privacy: str = "unlisted",
                 share_id: str | None = None) -> None:
        self.clip_dir = Path(clip_dir)
        self.store_root = Path(store_root)
        self.client = client
        self.title, self.app = title, app
        self.description, self.privacy = description, privacy
        self.share_id = share_id
        self.export: ExportReport | None = None
        self.outcome: UploadOutcome | None = None
        self.meta: ShareMetadata | None = None
        self._cancelled = False
        self.events: list[dict[str, Any]] = []

    # -- control ---------------------------------------------------------------------------

    def cancel(self) -> None:
        """The user pressed Cancel. Cooperative: checked between chunks by the client."""
        self._cancelled = True

    def _is_cancelled(self) -> bool:
        return self._cancelled

    # -- the run ---------------------------------------------------------------------------

    def run(self, *, progress: Callable[[int, int], None] | None = None) -> UploadOutcome:
        self.events.append({"stage": "begin", "clip": self.clip_dir.name})
        self.export = export_clip(self.clip_dir, self.store_root, share_id=self.share_id)
        self.events.append({"stage": "exported", "share_id": self.export.share_id,
                            "size_bytes": self.export.size_bytes,
                            "faststart": self.export.faststart})

        source_key = layout.read_key(layout.sidecars(self.clip_dir)["key"])
        self.meta = metadata_from_store_key(
            source_key, title=self.title, app=self.app,
            description=self.description, privacy=self.privacy)

        self.outcome = self.client.upload(
            self.export.path, self.meta, progress=progress, cancel=self._is_cancelled)
        self.events.append({"stage": "uploaded", **self.outcome.as_dict()})

        if not self.outcome.ok:
            # THE COMMIT IS CONDITIONED ON SUCCESS. Everything else removes itself.
            self._discard_export("upload-" + self.outcome.state)
            self.events.append({"stage": "discarded",
                                "reason": f"outcome={self.outcome.state}"})
            return self.outcome

        share_dir = self.export.path.parent
        _record_share(share_dir, self.outcome, self.meta)
        self.events.append({"stage": "committed", "share_dir": str(share_dir)})
        return self.outcome

    def _discard_export(self, reason: str) -> None:
        """Remove an uncommitted share directory entirely. Loud, and counted in bytes."""
        if self.export is None:
            return
        d = self.export.path.parent
        freed = layout.remove_clip_dir(d)
        print(f"SHARE_DISCARD share_id={self.export.share_id} reason={reason} "
              f"bytes_freed={freed}", flush=True)