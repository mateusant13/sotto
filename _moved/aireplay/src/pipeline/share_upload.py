"""share_upload.py -- THE INTERFACE, ONE REAL CLIENT, ONE FAKE THAT IS NOT A STUB.

================================================================================
THE INTERFACE IS THE PRODUCT. The service is replaceable; `UploadClient` is not.
================================================================================

`UploadClient.upload()` returns an `UploadOutcome` and NEVER raises for a transport
failure. That is the single most important line in this file, and it is the one a naive
implementation gets wrong:

    try: post(...)
    except Exception: pass          # <-- this is how an upload "succeeds" at 0 bytes

A caller that cannot tell "the bytes arrived" from "the socket died" cannot draw a line
between them either, so the local artefact gets committed and the user is told the clip is
on YouTube. `UploadOutcome.state` is the ONLY success signal, `SUCCEEDED` is the only value
that carries a `remote_id`, and every other state is a state.

================================================================================
THE FAKE IS THE PRIMARY PATH, NOT AN AFTERTHOUGHT.
================================================================================

The owner has issued no API keys and this lane will not invent any. So the fake carries the
whole gate, and it carries the failure modes the gate is BUILT to catch:

  * `fail_at_bytes` -- the network dies mid-transfer. The single most important negative:
    the outcome must NOT be SUCCEEDED, and the share must NOT be committed locally.
  * `cancel_at_bytes` -- the user hits Cancel. Nothing that looks like a finished share may
    survive it.
  * `remote_id` is `sha256(service + content)` -- deterministic, so the gate asserts a value
    rather than "something non-empty".

THE FAKE IS USABLE WITHOUT A NETWORK OR A CREDENTIAL. That is a property of its
construction (it reads the file the pipeline already wrote and hashes it) and the gate
proves it by running with the credential env var explicitly EMPTY.

================================================================================
THE REAL CLIENT -- YouTube Data API v3, `videos.insert`.
================================================================================

Everything below was READ from the discovery document, not recalled:
https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest , revision 20261006.

    videos.insert.path        'youtube/v3/videos'
    videos.insert.httpMethod  'POST'
    videos.insert.required    ['part']
    videos.insert.scopes      ['.../auth/youtube', '.../auth/youtube.force-ssl',
                               '.../auth/youtube.upload', '.../auth/youtubepartner']
    videos.insert.supportsMediaUpload  True
    rootUrl                   'https://youtube.googleapis.com/'
    servicePath               ''            <-- EMPTY, which is why the host is
                                                youtube.googleapis.com and NOT
                                                www.googleapis.com
    flatPath                  'youtube/v3/videos'
  Reference: https://developers.google.com/youtube/v3/docs/videos/insert
  Quota:     https://developers.google.com/youtube/v3/determine_quota_cost
             `videos.insert` costs 1600 units (the page's own summary: "ranging from 1 for
             actions such as `list` to 1600 for actions like `videos insert`"). A capture app
             that re-uploads a clip on every share spends its day's quota in ~9 uploads, so
             the number is printed by `describe()` rather than left in someone's memory.

  MEDIA_UPLOAD_URL is `rootUrl + "upload/" + flatPath` -- the `upload/` infix is Google's
  documented media-upload convention, and the discovery document supplies the two halves it
  is built from. It is a class attribute so a correction is one edit, not a hunt. It is
  labelled DERIVED in the receipt for exactly that reason.

CREDENTIALS. `access_token` is read from, in order: the constructor argument, the
environment variable named by `token_env_var` (default `YOUTUBE_ACCESS_TOKEN`), and then it
STOPS with `CredentialMissing` naming the variable. It never asks for one, never prompts,
never falls back to a default, and never writes one to disk. Every log line and every
exception this module raises passes through `_redact()`, so a token cannot reach the
console, a log file, or an `UploadOutcome.detail` by accident. `share_gate` ARM E proves
that with the token's own bytes as the search string.
"""

from __future__ import annotations

import abc
import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# See share_export.py for why `src/` (not a package) goes on sys.path and the siblings are
# imported as TOP-LEVEL names rather than through a `..parent` package that does not exist.
if __package__ in (None, ""):  # running the file directly
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.share_metadata import ShareMetadata  # noqa: E402

__all__ = [
    "UploadState", "UploadOutcome", "UploadClient", "CredentialMissing",
    "FakeUploadClient", "YouTubeUploadClient", "UploadCancelled",
    "CHUNK_BYTES", "describe_api_reference",
]

#: One transfer chunk. 8 MiB is the value the YouTube resumable-upload guide uses in its
#: own examples; the protocol does not require it, so it is a constant and not a claim.
CHUNK_BYTES = 8 * 1024 * 1024


class UploadState:
    """The vocabulary. Exactly one of these means 'the bytes are somebody else's now'."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUSED = "refused"          # never left this machine (no credential, bad metadata)

    ALL = (SUCCEEDED, FAILED, CANCELLED, REFUSED)


class UploadCancelled(Exception):
    """Raised inside a transfer when the cancel token fires. The client turns it into
    `UploadOutcome(state=CANCELLED)`. It is an exception because the transfer loop has to
    unwind; it never escapes `upload()`."""


class CredentialMissing(RuntimeError):
    """No credential. The message NAMES the variable and NEVER carries a value."""


@dataclass(frozen=True)
class UploadOutcome:
    """What happened. `state` is the only success signal; `remote_id` exists only on success."""

    state: str
    service: str
    remote_id: str = ""
    url: str = ""
    error_code: str = ""
    user_message: str = ""
    detail: str = ""
    bytes_sent: int = 0
    total_bytes: int = 0
    retryable: bool = False

    @property
    def ok(self) -> bool:
        return self.state == UploadState.SUCCEEDED

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state, "service": self.service, "remote_id": self.remote_id,
            "url": self.url, "error_code": self.error_code, "user_message": self.user_message,
            "detail": self.detail, "bytes_sent": self.bytes_sent, "total_bytes": self.total_bytes,
            "retryable": self.retryable, "ok": self.ok,
        }


ProgressFn = Callable[[int, int], None]
CancelFn = Callable[[], bool]


class UploadClient(abc.ABC):
    """The interface. One method, no exceptions for transport, no success-by-absence."""

    #: stable service id, e.g. 'youtube'
    service: str = "abstract"

    @abc.abstractmethod
    def upload(self, path: str | os.PathLike[str], meta: ShareMetadata, *,
               progress: ProgressFn | None = None,
               cancel: CancelFn | None = None) -> UploadOutcome:
        """PUT the file where the service can see it. Never raises for a transport failure."""

    def describe(self) -> dict[str, Any]:
        """Everything the surface may show about this destination before the user commits."""
        return {"service": self.service}


# ==================================================================================
# THE FAKE. No network, no credential, deterministic.
# ==================================================================================


class FakeUploadClient(UploadClient):
    """A complete, honest stand-in: it streams the real bytes and can fail on purpose.

    It is a DOUBLE, never `Provenance.REAL` -- the repo's own word for a test double
    (`pipeline/contracts.py:Provenance`). What makes it useful is that it can fail in the
    two places that matter and nowhere else, so a green gate means the PRODUCT's failure
    handling works rather than that the fake is polite.
    """

    service = "fake"

    def __init__(self, *, fail_at_bytes: int | None = None,
                 fail_reason: str = "network-error",
                 cancel_at_bytes: int | None = None,
                 chunk_bytes: int = CHUNK_BYTES) -> None:
        self.fail_at_bytes = fail_at_bytes
        self.fail_reason = fail_reason
        self.cancel_at_bytes = cancel_at_bytes
        self.chunk_bytes = chunk_bytes
        #: every call this instance made, so a gate can assert on the SEQUENCE, not just
        #: the last state -- e.g. that progress was reported before the failure
        self.calls: list[dict[str, Any]] = []

    def describe(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "is_real": False,
            "network": "none",
            "credentials": "none",
            "injected_failure_at_byte": self.fail_at_bytes,
            "injected_cancel_at_byte": self.cancel_at_bytes,
        }

    def upload(self, path: str | os.PathLike[str], meta: ShareMetadata, *,
               progress: ProgressFn | None = None,
               cancel: CancelFn | None = None) -> UploadOutcome:
        src = Path(path)
        try:
            total = src.stat().st_size
        except OSError as exc:
            return UploadOutcome(
                state=UploadState.REFUSED, service=self.service,
                error_code="unreadable-local-file",
                user_message="The clip to share could not be opened. Nothing was uploaded.",
                detail=f"stat failed: {exc}")

        meta.validate()
        sent = 0
        digest = hashlib.sha256()
        self.calls.append({"total_bytes": total, "title": meta.title})

        try:
            with open(src, "rb") as f:
                while True:
                    if cancel is not None and cancel():
                        raise UploadCancelled()
                    if self.cancel_at_bytes is not None and sent >= self.cancel_at_bytes:
                        raise UploadCancelled()
                    chunk = f.read(self.chunk_bytes)
                    if not chunk:
                        break
                    digest.update(chunk)
                    sent += len(chunk)
                    if progress is not None:
                        progress(sent, total)
                    if self.fail_at_bytes is not None and sent >= self.fail_at_bytes:
                        # The socket dies HERE. Everything above this line is what the
                        # service has; everything below never happened.
                        self.calls[-1]["failed_after_bytes"] = sent
                        return UploadOutcome(
                            state=UploadState.FAILED, service=self.service,
                            error_code=self.fail_reason,
                            user_message=("The upload was interrupted after "
                                          f"{sent} of {total} bytes. The clip is still on "
                                          "this PC — nothing was posted."),
                            detail=f"injected network failure at {sent}/{total} bytes",
                            bytes_sent=sent, total_bytes=total, retryable=True)
        except UploadCancelled:
            self.calls[-1]["cancelled_after_bytes"] = sent
            return UploadOutcome(
                state=UploadState.CANCELLED, service=self.service,
                error_code="cancelled-by-user",
                user_message=("Upload cancelled. The clip is still on this PC and nothing "
                              "was posted."),
                detail=f"cancelled at {sent}/{total} bytes",
                bytes_sent=sent, total_bytes=total)

        # Deterministic: same bytes + same service => same id, every run, every machine.
        remote = hashlib.sha256(
            f"{self.service}:{digest.hexdigest()}".encode("ascii")).hexdigest()[:16]
        return UploadOutcome(
            state=UploadState.SUCCEEDED, service=self.service, remote_id=remote,
            url=f"https://example.invalid/{self.service}/v/{remote}",
            user_message="Shared.", bytes_sent=sent, total_bytes=total)


# ==================================================================================
# THE REAL CLIENT. YouTube Data API v3 `videos.insert`, resumable.
# ==================================================================================


def describe_api_reference() -> dict[str, Any]:
    """The citations, as data, so the receipt and the code cannot drift apart."""
    return {
        "service": "youtube",
        "api": "YouTube Data API v3",
        "method": "videos.insert",
        "doc": "https://developers.google.com/youtube/v3/docs/videos/insert",
        "discovery": "https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest",
        "discovery_revision_read": "20261006",
        "path": "youtube/v3/videos",
        "http_method": "POST",
        "required_query_params": ["part"],
        "scope": "https://www.googleapis.com/auth/youtube.upload",
        "root_url": "https://youtube.googleapis.com/",
        "service_path": "",
        "supports_media_upload": True,
        "quota_units_per_call": 1600,
        "quota_doc": "https://developers.google.com/youtube/v3/determine_quota_cost",
        "privacy_enum": ["public", "unlisted", "private"],
    }


def _redact(text: str, secrets: tuple[str, ...]) -> str:
    """Blank out every secret. Called on every string that leaves this module."""
    out = text or ""
    for s in secrets:
        if s:
            out = out.replace(s, "<redacted>")
    return out


class YouTubeUploadClient(UploadClient):
    """Uploads one clip to YouTube as a video, resumably, in the background.

    WHAT IT DOES NOT DO, on purpose: it does not refresh tokens (that is an OAuth dance
    this lane has no credentials to perform), it does not set `selfDeclaredMadeForKids` from
    a guess, and it does not retry a non-idempotent call on its own. A retry belongs to the
    job, which knows whether the user pressed Share once or twice.
    """

    service = "youtube"

    #: DERIVED: rootUrl + "upload/" + flatPath, both read from the discovery document.
    #: See the module docstring and the receipt's "what is not claimed" section.
    MEDIA_UPLOAD_URL = "https://youtube.googleapis.com/upload/youtube/v3/videos"

    def __init__(self, access_token: str | None = None, *,
                 token_env_var: str = "YOUTUBE_ACCESS_TOKEN",
                 chunk_bytes: int = CHUNK_BYTES,
                 timeout_s: float = 60.0,
                 opener: Callable[[urllib.request.Request, float], Any] | None = None) -> None:
        self.token_env_var = token_env_var
        self.chunk_bytes = chunk_bytes
        self.timeout_s = timeout_s
        #: injectable so the gate can exercise request CONSTRUCTION with no network
        self._opener = opener or self._default_opener
        token = access_token if access_token is not None else os.environ.get(token_env_var, "")
        if not token.strip():
            raise CredentialMissing(
                f"no YouTube credential: set the environment variable {token_env_var} to an "
                f"OAuth 2.0 access token carrying the scope "
                f"'https://www.googleapis.com/auth/youtube.upload', or pass access_token= to "
                f"the constructor. This lane does not prompt, does not store one, and this "
                f"message deliberately carries no value."
            )
        self._token = token
        self._secrets = (token,)

    # -- internals -------------------------------------------------------------------------

    def _default_opener(self, req: urllib.request.Request, timeout: float) -> Any:
        creationflags = 0
        import sys
        if sys.platform == "win32":  # never a console window on the owner's screen
            creationflags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
        return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - fixed https host

    def _initiate_request(self, path: Path, meta: ShareMetadata) -> urllib.request.Request:
        """The first leg of a resumable upload. Pure function of (path, meta, token).

        Split out so the gate can assert on headers and body WITHOUT a network -- and so the
        token's own bytes can be searched for in everything this module would ever print.
        """
        from .share_metadata import to_youtube_video_resource

        resource = to_youtube_video_resource(meta)
        body = json.dumps(resource, ensure_ascii=False).encode("utf-8")
        size = path.stat().st_size
        qs = ("?uploadType=resumable&part=snippet,status"
              f"&notifySubscribers=false")
        req = urllib.request.Request(
            self.MEDIA_UPLOAD_URL + qs, data=body, method="POST",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(size),
                "User-Agent": "aireplay-share/1.0",
            })
        return req

    def _chunk_request(self, location: str, chunk: bytes, offset: int, total: int
                       ) -> urllib.request.Request:
        end = offset + len(chunk) - 1
        req = urllib.request.Request(
            location, data=chunk, method="PUT",
            headers={
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{end}/{total}",
                "User-Agent": "aireplay-share/1.0",
            })
        return req

    @staticmethod
    def _api_error(status: int, body: bytes) -> tuple[str, str]:
        """`{code, message}` out of the API's own error envelope, or a refusal to guess."""
        try:
            obj = json.loads(body.decode("utf-8", "replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return (f"http-{status}", "")
        err = obj.get("error") or {}
        reasons = [e.get("reason", "") for e in (err.get("errors") or []) if e.get("reason")]
        code = reasons[0] if reasons else (err.get("status") or f"http-{status}")
        return (str(code), str(err.get("message") or ""))

    #: API reason -> (user sentence, retryable?). Keys are `reason` values from the
    #: published error table for videos.insert; an unmapped reason falls through to the
    #: generic sentence rather than pretending to be understood.
    _REASONS: dict[str, tuple[str, bool]] = {
        "invalidTitle":        ("YouTube rejected the title. It is empty or longer than the service allows.", False),
        "mediaBodyRequired":   ("YouTube received no video data. The clip did not reach it.", True),
        "uploadLimitExceeded": ("This channel has hit its upload limit for today. Try tomorrow.", False),
        "forbidden":           ("YouTube refused the upload: this token cannot upload to this channel.", False),
        "forbiddenPrivacySetting": ("YouTube refused the privacy setting for this token.", False),
        "quotaExceeded":       ("The API's daily quota is spent (an upload costs 1600 units).", False),
        "dailyLimitExceeded":  ("This channel has hit its daily upload limit.", False),
        "authError":           ("The access token was rejected. Sign in again.", False),
        "rateLimitExceeded":   ("YouTube is rate limiting this token. Try again shortly.", True),
        "internalError":       ("YouTube had an internal error. The clip is safe on this PC.", True),
        "serviceUnavailable":  ("YouTube is unavailable right now. The clip is safe on this PC.", True),
    }

    def describe(self) -> dict[str, Any]:
        d = describe_api_reference()
        d.update({
            "is_real": True,
            "credentials": f"env:{self.token_env_var} (value never logged)",
            "endpoint": self.MEDIA_UPLOAD_URL,
            "upload_type": "resumable",
        })
        return d

    # -- the interface method --------------------------------------------------------------

    def upload(self, path: str | os.PathLike[str], meta: ShareMetadata, *,
               progress: ProgressFn | None = None,
               cancel: CancelFn | None = None) -> UploadOutcome:
        src = Path(path)
        total = src.stat().st_size if src.is_file() else 0
        if total == 0:
            return UploadOutcome(state=UploadState.REFUSED, service=self.service,
                                 error_code="empty-local-file",
                                 user_message="The clip is empty, so there was nothing to share.",
                                 detail=f"{src} is {total} bytes")

        def fail(code: str, message: str, detail: str, sent: int, retryable: bool
                 ) -> UploadOutcome:
            return UploadOutcome(
                state=UploadState.FAILED, service=self.service, error_code=code,
                user_message=message, detail=_redact(detail, self._secrets),
                bytes_sent=sent, total_bytes=total, retryable=retryable)

        # --- leg 1: open the resumable session -------------------------------------------
        try:
            resp = self._opener(self._initiate_request(src, meta), self.timeout_s)
            status = int(getattr(resp, "status", 200) or 200)
            headers = getattr(resp, "headers", {}) or {}
            location = headers.get("Location") or headers.get("location") or ""
            body = resp.read() if hasattr(resp, "read") else b""
        except urllib.error.HTTPError as exc:                      # the service said no
            raw = b""
            try:
                raw = exc.read()
            except Exception:  # noqa: BLE001 - the body is a nicety, the status is the fact
                pass
            code, message = self._api_error(exc.code, raw)
            human, retryable = self._REASONS.get(
                code, (f"YouTube refused the upload ({code}). The clip is still on this PC.",
                       500 <= exc.code < 600))
            return fail(code, human, _redact(message or str(exc), self._secrets), 0, retryable)
        except urllib.error.URLError as exc:
            # THE NETWORK LAYER. This is the branch a `try/except: pass` implementation
            # swallows, and it is the whole reason `state` exists.
            return fail("network-error",
                        "Could not reach YouTube. Nothing was uploaded — the clip is still "
                        "on this PC.", _redact(str(getattr(exc, 'reason', exc)), self._secrets),
                        0, True)
        except OSError as exc:
            return fail("network-error",
                        "Could not reach YouTube. Nothing was uploaded — the clip is still "
                        "on this PC.", _redact(str(exc), self._secrets), 0, True)

        if status not in (200, 201) or not location:
            code, message = self._api_error(status, body)
            return fail(code or f"http-{status}",
                        f"YouTube did not open an upload session ({status}). The clip is still "
                        f"on this PC.", _redact(message, self._secrets), 0, True)
        location = _redact(location, self._secrets)

        # --- leg 2..n: the bytes -----------------------------------------------------------
        sent = 0
        try:
            with open(src, "rb") as f:
                while True:
                    if cancel is not None and cancel():
                        raise UploadCancelled()
                    chunk = f.read(self.chunk_bytes)
                    if not chunk:
                        break
                    try:
                        r = self._opener(self._chunk_request(location, chunk, sent, total),
                                         self.timeout_s)
                        st = int(getattr(r, "status", 200) or 200)
                        rb = r.read() if hasattr(r, "read") else b""
                    except urllib.error.HTTPError as exc:
                        raw = b""
                        try:
                            raw = exc.read()
                        except Exception:  # noqa: BLE001
                            pass
                        code, message = self._api_error(exc.code, raw)
                        human, retryable = self._REASONS.get(
                            code, (f"YouTube rejected the upload ({code}).", False))
                        return fail(code, human, _redact(message or str(exc), self._secrets),
                                    sent, retryable)
                    except (urllib.error.URLError, OSError) as exc:
                        return fail("network-error",
                                    f"The connection dropped after {sent} of {total} bytes. "
                                    f"Nothing was posted — the clip is still on this PC.",
                                    _redact(str(getattr(exc, 'reason', exc)), self._secrets),
                                    sent, True)
                    if st not in (200, 201, 308):
                        code, message = self._api_error(st, rb)
                        return fail(code or f"http-{st}",
                                    f"YouTube rejected the upload ({st}).", message, sent, False)
                    sent += len(chunk)
                    if progress is not None:
                        progress(sent, total)
        except UploadCancelled:
            return UploadOutcome(
                state=UploadState.CANCELLED, service=self.service,
                error_code="cancelled-by-user",
                user_message="Upload cancelled. Nothing was posted — the clip is still on "
                             "this PC.",
                detail=f"cancelled at {sent}/{total} bytes",
                bytes_sent=sent, total_bytes=total)
        except OSError as exc:
            return fail("local-read-error", "The clip could not be read for upload.",
                        _redact(str(exc), self._secrets), sent, True)

        try:
            resource = json.loads(body.decode("utf-8", "replace")) if body else {}
        except json.JSONDecodeError:
            resource = {}
        video_id = str(resource.get("id") or "")
        if not video_id:
            # A 2xx with no id is NOT success. This is the "report success" trap in its
            # purest form, and it is checked rather than assumed.
            return fail("missing-remote-id",
                        "YouTube accepted the request but returned no video id. Not "
                        "counting this as shared.", _redact(body.decode("utf-8", "replace"),
                                                            self._secrets), total, True)

        return UploadOutcome(
            state=UploadState.SUCCEEDED, service=self.service, remote_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            user_message="Shared to YouTube.", bytes_sent=sent, total_bytes=total)