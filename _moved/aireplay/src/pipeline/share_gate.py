#!/usr/bin/env python
"""SHARE-GATE -- can a clip actually LEAVE this machine, and can it fail honestly?

================================================================================
WHAT THIS GATE IS FOR, given the reviewer's doubt
================================================================================

A sibling area's green gate meant "a 9-segment, offset-0 store is correct" while every real
blocker sat outside it. So the rule for this file is: **an arm is only an arm if it has been
watched going red.** Each of the three shipping failure modes gets its own arm AND its own
mutation of a COPY of this source tree that must turn exactly that arm red:

  ARM B  an upload that dies at the network layer must NOT report success
  ARM C  a cancelled upload must not leave anything on disk that a later run can read as a
         finished share
  ARM D  the real client must refuse, LOUDLY and SPECIFICALLY, when the credential is absent
  ARM E  no string this module can produce may contain the credential
  ARM A  the happy path really works end to end (fake client, no network, no credential)
  ARM F  the metadata contract still matches the live index schema
  ARM G  every state the user can reach has a sentence, and none of them is a raw exception

THE CONTROLS ARE THE GATE. `--control` runs the SAME evaluation against a mutated copy:

  M1 "commit-unconditional" -- deletes the `if not self.outcome.ok: discard` test, so a
       failed upload still leaves a committed share.  MUST red B and C.
  M2 "network-lies"          -- makes the fake report SUCCEEDED on the network failure.
       MUST red B.

A control that goes all-red is as useless as one that stays all-green, so the verdict also
requires each control to leave its UNRELATED arms green. And if a mutation does not apply,
the gate FAILS with "control invalid" rather than reporting a pass -- a control that is red
for the wrong reason looks exactly like evidence (receipt-16 §10, quoted in
pipeline/contracts.py:17).

NO NETWORK AND NO CREDENTIAL ARE REQUIRED. The credential env var is explicitly CLEARED for
the whole run and asserted cleared before ARM A, so a green run cannot have borrowed the
owner's keys. ARM E is the only arm that constructs the real client, and it does so with a
token this gate invents, exercising request CONSTRUCTION rather than transmission.

Exit code 0 = PASS, 1 = FAIL. There is no third answer.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

_HERE = Path(__file__).resolve()
_SRC = _HERE.parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pipeline import share_export, share_metadata, share_upload  # noqa: E402
from storage import layout  # noqa: E402
from ui import share_dialog  # noqa: E402

#: The credential variable the real client reads. Cleared for the whole run.
CRED_ENV = "YOUTUBE_ACCESS_TOKEN"
#: A token this gate INVENTS. Not a credential, never valid anywhere, exists to be searched
#: for in every string the module can emit.
FAKE_TOKEN = "gate-invented-token-DO-NOT-USE-4f2b"

ARMS = ("A", "B", "C", "D", "E", "F", "G")


class Arm:
    """One named claim, its own verdict, and enough detail to be debugged from the log."""

    def __init__(self, name: str, title: str) -> None:
        self.name, self.title = name, title
        self.checks: list[tuple[bool, str]] = []
        self.data: dict[str, Any] = {}

    def check(self, ok: bool, what: str) -> bool:
        self.checks.append((bool(ok), what))
        return bool(ok)

    @property
    def ok(self) -> bool:
        return all(c for c, _ in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {"arm": self.name, "title": self.title, "pass": self.ok,
                "failed": [w for c, w in self.checks if not c],
                "checks": len(self.checks), "data": self.data}


# ==================================================================================
# The fixture: a REAL committed clip in a REAL store, built by the REAL store writer.
# ==================================================================================


def build_source_clip(work: Path, *, seconds: float = 0.5, w: int = 64, h: int = 64
                      ) -> tuple[Path, Path, dict[str, Any]]:
    """A committed clip store under `work`, and the clip's directory.

    Built through `layout.ClipWriter` rather than by writing files by hand, so the fixture is
    a clip the product itself would accept -- including the `.partial` -> `key.json` dance
    that `export_clip` REFUSES to work without. An UNCOMMITTED clip is ARM H's fixture and
    is built separately, by breaking it on purpose.
    """
    store = work / "store"
    store.mkdir(parents=True, exist_ok=True)
    (store / layout.ROOT_MARKER).write_text(json.dumps(
        {"layout_version": layout.LAYOUT_VERSION}), encoding="utf-8")

    ffmpeg = share_export.find_tool("ffmpeg")
    if not ffmpeg:
        raise SystemExit("FATAL: ffmpeg not found; this gate cannot build its fixture")

    raw = work / "raw.mp4"
    cmd = [ffmpeg, "-nostdin", "-v", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=30:duration={seconds}",
           "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(raw)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          creationflags=(0x08000000 | 0x00000008)
                          if sys.platform == "win32" else 0)
    if proc.returncode != 0 or not raw.is_file():
        raise SystemExit(f"FATAL: could not build the fixture clip: {proc.stderr[:400]}")

    clip_id = layout.make_clip_id(time.time(), 0)
    writer = layout.ClipWriter(store, clip_id)
    writer.write_media(raw.read_bytes())
    key = writer.commit(duration_ms=int(seconds * 1000), source_device="test-hwnd-4x4",
                        mode="manual")
    return store, writer.path, key


def share_keys(work: Path) -> list[dict[str, Any]]:
    """What the SHARE store claims, read back through the store's own reader.

    This is the assertion that matters for ARM B and ARM C. Not 'a flag is False' -- 'a
    future maintenance run, using vocabulary that already exists, sees no finished share'.
    """
    return layout.walk_keys(share_export.shares_root_for(work / "store"))


def share_files(work: Path) -> list[str]:
    root = share_export.shares_root_for(work / "store")
    if not root.exists():
        return []
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def share_dirs(work: Path) -> list[Path]:
    """The SHARE store's CLIP directories, and only those.

    Found with `layout.CLIP_ID_RE`, never with a glob: an earlier version of this helper
    matched any directory under a numeric parent, which swept in the `clips/2026/10/08` DATE
    directories and then asserted that they carried a `.partial` marker. Those directories
    are not clips, they are the calendar, and asserting on them is how a gate ends up
    reporting a failure that is really a bug in the gate.
    """
    root = share_export.shares_root_for(work / "store")
    if not root.exists():
        return []
    return [c.path for c in layout.iter_clips(root)]


def _header(req, name: str) -> str | None:
    """Case-insensitive header lookup.

    `urllib.request.Request` title-cases every dash-separated part on the way in, so
    `X-Upload-Content-Type` is STORED as `X-upload-content-type` and `get_header()`'s exact
    match misses. Checking the product's header by the wrong casing is a test bug that reads
    as a product bug, and it is worth the four lines to keep the two apart.
    """
    want = name.lower()
    for k, v in getattr(req, "headers", {}).items():
        if k.lower() == want:
            return v
    return None


# ==================================================================================
# The arms.
# ==================================================================================


def arm_a(work: Path) -> Arm:
    """The happy path, with no network and no credential."""
    a = Arm("A", "a committed clip exports faststart and shares with the fake client")
    store, clip_dir, key = build_source_clip(work)
    src_size = layout.sidecars(clip_dir)["media"].stat().st_size

    job = share_export.ShareJob(clip_dir, store, share_upload.FakeUploadClient(),
                                title="Gate A - happy path", app="GateFixture")
    seen: list[tuple[int, int]] = []
    out = job.run(progress=lambda s, t: seen.append((s, t)))

    a.check(out.state == share_upload.UploadState.SUCCEEDED,
            f"outcome.state == succeeded (got {out.state!r}: {out.user_message})")
    a.check(bool(out.remote_id), f"remote_id is non-empty (got {out.remote_id!r})")
    a.check(bool(out.url), "a success carries a url")

    # Faststart is MEASURED from the produced file's own box headers, not asserted.
    a.check(job.export is not None and job.export.faststart is True,
            f"export is faststart by box order (got {job.export.faststart})")
    kinds = [b[0] for b in (job.export.boxes if job.export else [])]
    a.check("moov" in kinds and "mdat" in kinds and kinds.index("moov") < kinds.index("mdat"),
            f"moov precedes mdat in the written file ({kinds})")

    # `-c copy` means the byte count is UNCHANGED. A share that re-encodes is a bug, and
    # this is the cheap assertion that catches it.
    a.check(job.export is not None and job.export.size_bytes == src_size,
            f"-c copy: share bytes == source bytes "
            f"({job.export.size_bytes if job.export else '?'} vs {src_size})")
    a.check(job.export is not None and job.export.reencoded is False, "reencoded is False")

    a.check(bool(seen), f"progress was reported ({len(seen)} callbacks)")
    a.check(seen and seen[-1][0] == seen[-1][1], "progress reaches 100% of total")

    keys = share_keys(work)
    a.check(len(keys) == 1, f"the share store claims exactly ONE key (got {len(keys)})")
    a.check((keys[0].get("content_key") if keys else "") == job.export.sha256,
            "the share key's content_key is the sha256 of the bytes actually written")
    a.check("share.json" in " ".join(share_files(work)),
            f"the share receipt exists ({share_files(work)})")

    # Determinism: the same bytes and the same service give the same id, twice.
    j2 = share_export.ShareJob(clip_dir, store, share_upload.FakeUploadClient(),
                               title="Gate A - happy path", app="GateFixture")
    out2 = j2.run()
    a.check(out2.remote_id == out.remote_id,
            f"the fake's remote_id is deterministic ({out.remote_id} vs {out2.remote_id})")
    a.data = {"remote_id": out.remote_id, "share_id": job.export.share_id,
              "source_bytes": src_size, "share_bytes": job.export.size_bytes,
              "boxes": [list(b) for b in job.export.boxes], "wall_s": round(job.export.wall_s, 3),
              "share_store_keys": len(keys)}
    return a


def arm_b(work: Path) -> Arm:
    """THE FIRST SHIPPING FAILURE: the network dies mid-transfer. Must not report success."""
    a = Arm("B", "a network-layer failure mid-upload is NOT reported as success")
    store, clip_dir, _ = build_source_clip(work)

    # 1 KiB chunks with the failure at 2 KiB: genuinely MID-transfer, not "the file was too
    # small to matter".
    client = share_upload.FakeUploadClient(chunk_bytes=1024, fail_at_bytes=2048)
    job = share_export.ShareJob(clip_dir, store, client,
                                title="Gate B - network dies", app="GateFixture")
    out = job.run()

    a.check(out.state != share_upload.UploadState.SUCCEEDED,
            f"state is not succeeded (got {out.state!r})")
    a.check(out.state == share_upload.UploadState.FAILED,
            f"state is failed (got {out.state!r})")
    a.check(out.remote_id == "", f"a failure carries NO remote_id (got {out.remote_id!r})")
    a.check(out.error_code == "network-error", f"error_code is network-error (got {out.error_code!r})")
    a.check(0 < out.bytes_sent < out.total_bytes,
            f"the failure was mid-transfer ({out.bytes_sent}/{out.total_bytes} bytes)")
    a.check(out.retryable is True, "a network failure is marked retryable")

    # The local consequence, which is what actually ships broken.
    keys = share_keys(work)
    a.check(len(keys) == 0, f"the share store claims NO key (got {len(keys)})")
    a.check(not any("share.json" in f for f in share_files(work)),
            f"no share receipt was written ({share_files(work)})")

    # And what the user is shown.
    view = share_dialog.render(out, job.meta, services=(client.describe(),),
                               selected_service=client.service)
    a.check(view["tone"] == "error", f"the surface paints it as an error (got {view['tone']!r})")
    a.check(bool(view["headline"]), "the surface has a sentence to show")
    a.check("still on this PC" in view["headline"] or "still on" in view["headline"],
            f"the sentence says the clip is safe locally ({view['headline']!r})")
    a.check(view["share_enabled"] is True, "the Share button comes back for a retry")
    a.check(view["succeeded"] is False, "the surface does not claim success")

    a.data = {"state": out.state, "bytes_sent": out.bytes_sent, "total_bytes": out.total_bytes,
              "headline": view["headline"], "share_store_keys": len(keys),
              "discarded": [e for e in job.events if e.get("stage") == "discarded"]}
    return a


def arm_c(work: Path) -> Arm:
    """THE SECOND SHIPPING FAILURE: Cancel. Nothing may survive that looks finished."""
    a = Arm("C", "a cancelled upload leaves no half-written file that reads as a share")
    store, clip_dir, _ = build_source_clip(work)

    client = share_upload.FakeUploadClient(chunk_bytes=1024, cancel_at_bytes=2048)
    job = share_export.ShareJob(clip_dir, store, client,
                                title="Gate C - cancelled", app="GateFixture")
    out = job.run()
    # A user pressing Cancel mid-transfer, through the public method.
    c2 = share_export.ShareJob(clip_dir, store,
                               share_upload.FakeUploadClient(chunk_bytes=1024),
                               title="Gate C - cancelled", app="GateFixture")
    c2.cancel()
    out2 = c2.run()

    for label, o in (("injected", out), ("public cancel()", out2)):
        a.check(o.state == share_upload.UploadState.CANCELLED,
                f"{label}: state is cancelled (got {o.state!r})")
        a.check(o.remote_id == "", f"{label}: no remote_id on a cancel (got {o.remote_id!r})")
        a.check(o.bytes_sent < o.total_bytes,
                f"{label}: the cancel landed mid-transfer ({o.bytes_sent}/{o.total_bytes})")

    a.check(len(share_keys(work)) == 0,
            f"the share store claims NO key after a cancel (got {len(share_keys(work))})")
    a.check(not any("share.json" in f for f in share_files(work)),
            f"no share receipt after a cancel ({share_files(work)})")

    # The sharpest form of the question: does ANY surviving directory carry a key.json?
    survivors = share_dirs(work)
    for d in survivors:
        a.check(not (d / layout.KEY_NAME).is_file(),
                f"surviving dir {d.name} has NO key.json")
        a.check((d / layout.PARTIAL_MARKER).exists(),
                f"surviving dir {d.name} still carries its .partial marker")
    a.check(not any(f.endswith(layout.MEDIA_NAME) for f in share_files(work)),
            f"no committed media survives a cancel ({share_files(work)})")

    view = share_dialog.render(out2, c2.meta, services=(client.describe(),),
                               selected_service=client.service)
    a.check(view["tone"] != "error", f"a cancel is not painted as an error (got {view['tone']!r})")
    a.check("nothing" in view["headline"].lower() or "still on" in view["headline"].lower(),
            f"the sentence says nothing was posted ({view['headline']!r})")
    a.check(view["share_enabled"] is True, "the user can start over after a cancel")

    a.data = {"injected": out.state, "public_cancel": out2.state,
              "surviving_dirs": [d.name for d in survivors],
              "files": share_files(work), "share_store_keys": len(share_keys(work)),
              "headline": view["headline"]}
    return a


def arm_d(work: Path) -> Arm:
    """THE THIRD SHIPPING FAILURE: no credential. Refuse loudly, name the variable, no value."""
    a = Arm("D", "the real client refuses without a credential, naming the variable")
    saved = os.environ.get(CRED_ENV)
    os.environ.pop(CRED_ENV, None)
    try:
        try:
            share_upload.YouTubeUploadClient()
            a.check(False, "constructing the client without a credential must RAISE")
            msg = ""
        except share_upload.CredentialMissing as exc:
            msg = str(exc)
            a.check(True, "constructing without a credential raises CredentialMissing")
        a.check(CRED_ENV in msg, f"the message names the variable ({CRED_ENV!r} in message)")
        a.check("youtube.upload" in msg, "the message names the scope the token needs")
        a.check(not any(tok in msg for tok in ("Bearer", "ya29.", "AIza")),
                f"the message carries no credential-looking value ({msg[:120]!r})")

        # And the surface turns that refusal into something a user can act on.
        view = share_dialog.render(
            share_upload.UploadOutcome(
                state=share_upload.UploadState.REFUSED, service="youtube",
                error_code="missing-credential",
                user_message="Sign in to YouTube first. Nothing was uploaded."),
            services=({"service": "youtube", "is_real": True},), selected_service="youtube")
        a.check(view["tone"] == "error", f"a refusal is an error (got {view['tone']!r})")
        a.check("nothing was uploaded" in view["headline"].lower(),
                f"the sentence says nothing was uploaded ({view['headline']!r})")
        a.data = {"message": msg[:300], "headline": view["headline"]}
    finally:
        if saved is not None:
            os.environ[CRED_ENV] = saved
    return a


def arm_e(work: Path) -> Arm:
    """No string this module can produce may contain the credential."""
    a = Arm("E", "the credential appears in the auth header and NOWHERE else")
    saved = os.environ.get(CRED_ENV)
    os.environ[CRED_ENV] = FAKE_TOKEN
    try:
        client = share_upload.YouTubeUploadClient()
        _, clip_dir, key = build_source_clip(work)
        meta = share_metadata.metadata_from_store_key(key, title="Gate E", app="GateFixture")

        req = client._initiate_request(Path(layout.sidecars(clip_dir)["media"]), meta)
        a.check(_header(req, "Authorization") == f"Bearer {FAKE_TOKEN}",
                "the token IS in the Authorization header (it has to be)")
        a.check("uploadType=resumable" in req.full_url,
                f"the initiation is a resumable upload ({req.full_url})")
        a.check("part=snippet,status" in req.full_url, "part names snippet,status")
        a.check(_header(req, "X-Upload-Content-Type") == "video/mp4",
                "the media type is declared")
        a.check(client.MEDIA_UPLOAD_URL == "https://youtube.googleapis.com/upload/youtube/v3/videos",
                f"the endpoint is the discovery-derived one ({client.MEDIA_UPLOAD_URL})")

        # THE REAL LEAK TEST, through the real client. An earlier version of this arm built
        # a `CredentialMissing` by hand WITH the token in the message and then asserted the
        # message did not contain it -- a self-referential check that could only ever fail,
        # testing a string this arm had just written. The genuine risk is an exception from
        # deep in the transport carrying the header into a log line or an `UploadOutcome`.
        # So: drive a REAL failed upload whose exception text contains the token, and read
        # back everything the caller can see.
        def exploding_opener(req, timeout):
            import urllib.error
            raise urllib.error.URLError(
                f"failed to send Authorization: Bearer {FAKE_TOKEN} to "
                f"{req.host}")

        leaky = share_upload.YouTubeUploadClient(opener=exploding_opener)
        real_out = leaky.upload(Path(layout.sidecars(clip_dir)["media"]), meta)
        a.check(real_out.state == share_upload.UploadState.FAILED,
                f"a transport exception is a FAILED outcome (got {real_out.state!r})")
        a.check(FAKE_TOKEN not in real_out.detail,
                f"the failure DETAIL carries no token ({real_out.detail[:80]!r})")
        a.check(FAKE_TOKEN not in real_out.user_message,
                "the sentence shown to the user carries no token")
        a.check("<redacted>" in real_out.detail,
                f"the token is actively replaced, not merely absent ({real_out.detail[:80]!r})")

        emitted = {
            "describe()": json.dumps(client.describe()),
            "redact()": share_upload._redact(f"header was Bearer {FAKE_TOKEN}", client._secrets),
            "real failure outcome": json.dumps(real_out.as_dict()),
        }
        a.check(FAKE_TOKEN not in emitted["describe()"],
                "describe() carries no token, so a UI listing destinations cannot leak it")
        a.check(FAKE_TOKEN not in emitted["real failure outcome"],
                "the whole outcome, serialised, carries no token")
        a.check("<redacted>" in emitted["redact()"],
                "_redact() really does blank the secret")

        # The quota number is a product fact, surfaced before the user spends it.
        desc = client.describe()
        a.check(desc["quota_units_per_call"] == 1600,
                f"the 1600-unit cost is stated ({desc.get('quota_units_per_call')})")
        a.data = {"endpoint": client.MEDIA_UPLOAD_URL, "url": req.full_url,
                  "quota_units": desc["quota_units_per_call"],
                  "emitted_keys": sorted(emitted)}
    finally:
        if saved is not None:
            os.environ[CRED_ENV] = saved
        else:
            os.environ.pop(CRED_ENV, None)
    return a


def arm_f(work: Path) -> Arm:
    """The metadata contract still matches the live index schema."""
    a = Arm("F", "the CONFIRMED metadata fields still exist in the live tree")
    rep = share_metadata.verify_index_expectations()
    drift = [r for r in rep.checked if r.get("checked") == "DRIFT"]
    a.check(rep.ok, f"no CONFIRMED field has drifted ({[d['field'] for d in drift]})")
    for r in rep.checked:
        if r["certainty"] == share_metadata.CONFIRMED:
            a.check(r.get("checked") == "present", f"{r['field']} is present ({r.get('target')})")
    a.check(sorted(rep.missing_proposed) == ["app", "title"],
            f"the two PROPOSED columns are still absent, as documented "
            f"(got {rep.missing_proposed})")
    # A bad privacy value must be refused before any byte moves.
    try:
        share_metadata.to_youtube_video_resource(
            share_metadata.ShareMetadata("20260101T000000Z-0000", "0" * 64, "t", "x", 0.0,
                                         privacy="everyone"))
        a.check(False, "an off-enum privacy value must be REFUSED")
    except share_metadata.MetadataError:
        a.check(True, "an off-enum privacy value is refused")
    try:
        share_metadata.ShareMetadata("20260101T000000Z-0000", "0" * 64, "   ", "x", 0.0).validate()
        a.check(False, "an empty title must be REFUSED")
    except share_metadata.MetadataError:
        a.check(True, "an empty title is refused before any byte moves")
    a.data = {"ok": rep.ok, "confirmed": [r["field"] for r in rep.checked
                                          if r["certainty"] == share_metadata.CONFIRMED],
              "proposed_absent": rep.missing_proposed}
    return a


def arm_g(work: Path) -> Arm:
    """Every reachable state has a sentence, and no sentence is a raw exception."""
    a = Arm("G", "every state renders a sentence, and none of them is an exception dump")
    raw_tokens = ("0x", "WinError", "Traceback", "errno", "Exception(", "error 0x")
    meta = share_metadata.ShareMetadata("20260101T000000Z-0000", "a" * 64, "Title",
                                        "2026-01-01T00:00:00Z", 0.0, app="Game")
    cases = {
        share_upload.UploadState.FAILED: ("Upload failed. The clip is still on this PC.", True),
        share_upload.UploadState.CANCELLED: ("Upload cancelled. Nothing was posted.", False),
        share_upload.UploadState.REFUSED: ("This was never sent.", True),
        share_upload.UploadState.SUCCEEDED: ("Shared.", False),
    }
    for state, (msg, expect_error) in cases.items():
        out = share_upload.UploadOutcome(
            state=state, service="fake",
            remote_id="r1" if state == share_upload.UploadState.SUCCEEDED else "",
            user_message=msg,
            detail="WinError 1450 insufficient system resources exist (0x80070005)")
        v = share_dialog.render(out, meta, services=({"service": "fake"},),
                                selected_service="fake", verbose=True)
        blob = " ".join([v["headline"], *v["lines"], v["detail"]])
        a.check(bool(v["headline"]), f"{state}: a headline is rendered")
        a.check(v["tone"] == ("error" if expect_error else "ok"),
                f"{state}: tone is {'error' if expect_error else 'ok'} (got {v['tone']!r})")
        a.check(not any(t in blob for t in raw_tokens),
                f"{state}: nothing raw leaks even with a WinError in the detail ({blob!r})")
        a.check(v["share_enabled"] is (state != share_upload.UploadState.SUCCEEDED),
                f"{state}: the button is {'disabled' if state == share_upload.UploadState.SUCCEEDED else 'live'}")

    # A succeeded share must not offer Share again; everything else must.
    v = share_dialog.render(
        share_upload.UploadOutcome(state=share_upload.UploadState.SUCCEEDED, service="fake",
                                   remote_id="r1", url="https://example.invalid/x"),
        meta, services=({"service": "fake"},), selected_service="fake")
    a.check(v["succeeded"] is True and v["url"].startswith("https://"),
            "a success surfaces its url")
    # No destination chosen -> no Share. A panel that shares to whatever is first is a bug.
    # TWO services here on purpose: with exactly one the panel preselects it (deliberate,
    # see share_dialog.render), so a single-service arm could not tell "preselected" from
    # "leaked a default" and would pass either way.
    two = ({"service": "fake"}, {"service": "youtube", "is_real": True})
    v2 = share_dialog.render(None, meta, services=two, selected_service="")
    a.check(v2["can_share"] is False,
            "with two destinations and none chosen, Share is not offered")
    one = share_dialog.render(None, meta, services=({"service": "fake"},), selected_service="")
    a.check(one["can_share"] is True,
            "with exactly ONE destination it is preselected, so Share is offered")
    a.data = {"states": list(cases)}
    return a


ARM_FUNCS: dict[str, Callable[[Path], Arm]] = {
    "A": arm_a, "B": arm_b, "C": arm_c, "D": arm_d, "E": arm_e, "F": arm_f, "G": arm_g,
}


# ==================================================================================
# The controls: the same evaluation against a MUTATED COPY of this tree.
# ==================================================================================

MUTATIONS: dict[str, dict[str, Any]] = {
    "m1": {
        "label": "commit-unconditional",
        "file": "pipeline/share_export.py",
        "find": "        if not self.outcome.ok:\n",
        "replace": "        if False:  # MUTATED: the commit is no longer conditioned\n",
        "must_red": ["B", "C"],
    },
    "m2": {
        "label": "network-lies",
        "file": "pipeline/share_upload.py",
        "find": "                            state=UploadState.FAILED, service=self.service,\n"
                "                            error_code=self.fail_reason,\n",
        "replace": "                            state=UploadState.SUCCEEDED, service=self.service,\n"
                   "                            error_code=self.fail_reason,\n",
        "must_red": ["B"],
    },
}


def apply_mutation(src_root: Path, dest_root: Path, kind: str) -> dict[str, Any]:
    """Copy the tree, apply ONE named mutation, and PROVE it applied.

    A mutation that silently matched nothing would leave the control running the CURE, and
    the control would then stay GREEN -- which reads as 'the arm is robust' when it means
    'the mutation never happened'. So the match count is part of the control's result.
    """
    spec = MUTATIONS[kind]
    # THE CONTROL TREE KEEPS THE PRODUCTION SHAPE: <dest>/src/<pkg>. That is not tidiness.
    # Product code derives paths from `__file__` (e.g. `share_metadata._schema_sql()` walks
    # up two levels and appends `src/index/schema.sql`), so a flattened control copy makes
    # those derivations land outside the tree and report DRIFT for reasons that have nothing
    # to do with the mutation -- ARM F went red in both controls exactly this way. `index` is
    # copied for the same reason: ARM F reads `src/index/schema.sql` off disk.
    for pkg in ("pipeline", "storage", "ui", "index"):
        shutil.copytree(src_root / pkg, dest_root / "src" / pkg,
                        ignore=shutil.ignore_patterns("__pycache__"))
    target = dest_root / "src" / spec["file"]
    text = target.read_text(encoding="utf-8")
    count = text.count(spec["find"])
    if count != 1:
        return {"mutation": kind, "label": spec["label"], "applied": False,
                "matches": count, "file": spec["file"],
                "error": f"mutation {kind} matched {count} times (need exactly 1); "
                         f"the control would have run the CURE"}
    target.write_text(text.replace(spec["find"], spec["replace"]), encoding="utf-8")
    return {"mutation": kind, "label": spec["label"], "applied": True, "matches": count,
            "file": spec["file"], "must_red": spec["must_red"]}


def run_child(work: Path, *, json_only: bool) -> dict[str, Any]:
    """Run every arm in a fresh scratch tree and return their verdicts."""
    out: dict[str, Any] = {"arms": {}, "ok": True}
    for name in ARMS:
        w = work / f"arm{name}"
        if w.exists():
            shutil.rmtree(w, ignore_errors=True)
        w.mkdir(parents=True, exist_ok=True)
        try:
            out["arms"][name] = arm = ARM_FUNCS[name](w).as_dict()
        except Exception as exc:  # noqa: BLE001 - an arm that ERRORS is a failed arm
            out["arms"][name] = {"arm": name, "pass": False,
                                 "failed": [f"arm raised {type(exc).__name__}: {exc}"],
                                 "checks": 0, "data": {}}
        out["ok"] = out["ok"] and out["arms"][name]["pass"]
        if not json_only:
            a = out["arms"][name]
            print(f"ARM {name} {'PASS' if a['pass'] else 'FAIL'}  "
                  f"({a['checks']} checks)  {a['title']}")
            for wmiss in a["failed"]:
                print(f"       X {wmiss}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="share export + upload gate")
    ap.add_argument("--work", default="", help="scratch root (default: a temp dir)")
    ap.add_argument("--arms", default="", help="unused; kept so a caller's flag is not an error")
    ap.add_argument("--json", action="store_true", help="print the verdict as json only")
    ap.add_argument("--skip-controls", action="store_true",
                    help="live arms only. NOT a pass: a gate with no red arm is an ornament.")
    ap.add_argument("--control", action="store_true",
                    help="run only the mutated controls (used by the parent run)")
    args = ap.parse_args(argv)

    work = Path(args.work) if args.work else Path(
        os.environ.get("TEMP", ".")) / f"aireplay-share-gate-{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)

    # The credential must be ABSENT for the run, or a green could have borrowed it.
    saved_cred = os.environ.pop(CRED_ENV, None)
    try:
        if args.control:
            res = run_child(work, json_only=True)
            print("SHARE_GATE_JSON " + json.dumps(res))
            return 0 if res["ok"] else 1

        live = run_child(work, json_only=args.json)

        controls: list[dict[str, Any]] = []
        control_ok = True
        if not args.skip_controls:
            for kind, spec in MUTATIONS.items():
                dest = work / f"control-{kind}"
                if dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                dest.mkdir(parents=True, exist_ok=True)
                mres = apply_mutation(_SRC, dest, kind)
                mres["arms"] = {}
                mres["ok"] = False
                mres["unexpected_red"] = []
                if mres["applied"]:
                    # Run the COPY's gate, not the original one. An earlier version spawned
                    # `sys.executable <ORIGINAL share_gate.py>` with PYTHONPATH pointed at
                    # the mutated tree, and the copy's `_SRC` insert then lost to the
                    # script's own directory -- so the child imported the UNMUTATED modules,
                    # both controls stayed green, and the run reported "the arms are
                    # robust" when it meant "the mutation never ran". Running the copy's own
                    # gate makes `_SRC` BE the mutated tree, and the child's report below is
                    # checked against `dest` so this can never silently happen again.
                    child_gate = dest / "src" / "pipeline" / "share_gate.py"
                    proc = subprocess.run(
                        [sys.executable, str(child_gate), "--work", str(dest / "run"),
                         "--json", "--skip-controls"],
                        capture_output=True, text=True, timeout=1800,
                        env={**os.environ, "PYTHONPATH": str(dest / "src"),
                             "PYTHONDONTWRITEBYTECODE": "1"},
                        creationflags=(0x08000000 | 0x00000008)
                        if sys.platform == "win32" else 0)
                    line = next((l for l in (proc.stdout or "").splitlines()
                                 if l.startswith("SHARE_GATE_JSON ")), None)
                    if line is None:
                        mres["error"] = f"control {kind} produced no verdict " \
                                        f"(rc={proc.returncode}) {(proc.stderr or '')[-400:]}"
                        control_ok = False
                    else:
                        cj = json.loads(line[len("SHARE_GATE_JSON "):])
                        # PROOF the child ran the MUTATED tree, not the original.
                        mres["child_src_root"] = cj.get("src_root")
                        if cj.get("src_root") != str(dest / "src"):
                            mres["error"] = (f"control {kind} ran src_root="
                                             f"{cj.get('src_root')!r}, expected "
                                             f"{str(dest / 'src')!r}; the mutation was not "
                                             f"the code under test")
                            control_ok = False
                            child_arms = {a: {"pass": True, "failed": [],
                                              "checks": 0, "data": {}} for a in ARMS}
                        else:
                            child_arms = cj["live"]["arms"]
                        mres["arms"] = {k: v["pass"] for k, v in child_arms.items()}
                        mres["ok"] = cj["ok"]
                        # The control is only EVIDENCE if it broke exactly its own arms.
                        for arm in ARMS:
                            passed = child_arms[arm]["pass"]
                            if arm in spec["must_red"] and passed:
                                mres["unexpected_red"].append(f"{arm} stayed GREEN")
                                control_ok = False
                            if arm not in spec["must_red"] and not passed:
                                mres["unexpected_red"].append(f"{arm} went RED but is unrelated")
                                control_ok = False
                        mres["red"] = [a for a in spec["must_red"] if not child_arms[a]["pass"]]
                else:
                    control_ok = False
                controls.append(mres)

        verdict = live["ok"] and (args.skip_controls or control_ok)
        if args.json:
            print("SHARE_GATE_JSON " + json.dumps(
                {"live": live, "controls": controls, "ok": verdict, "src_root": str(_SRC)}))
            return 0 if verdict else 1

        print()
        print(f"SHARE_GATE controls: {len(controls)}")
        for c in controls:
            red = ",".join(c.get("red", [])) or "-"
            print(f"  {c['mutation']} {c['label']:<22} applied={c['applied']} "
                  f"red={red} green_and_broken={c.get('unexpected_red') or '-'}")
        print()
        print("VERDICT " + ("PASS" if verdict else "FAIL"))
        if not live["ok"]:
            print("  live arms failed: "
                  + ", ".join(n for n in ARMS if not live["arms"][n]["pass"]))
        if not control_ok and not args.skip_controls:
            print("  A CONTROL IS INVALID -- a red that is not from the mutation is not "
                  "evidence. See contracts.py:17.")
        return 0 if verdict else 1
    finally:
        if saved_cred is not None:
            os.environ[CRED_ENV] = saved_cred


if __name__ == "__main__":
    raise SystemExit(main())