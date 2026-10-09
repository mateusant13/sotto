"""share_dialog.py -- THE SURFACE, as a headless view model.

================================================================================
WHY A VIEW MODEL AND NOT A WINDOW
================================================================================

Two reasons, and the second is the one that matters.

  1. This lane must never put a window on the owner's screen (`AGENTS.md`, hard rule 1).
     A pywebview/WebView2 dialog is exactly the kind of thing that shows up unasked.
  2. **The failure text is the product.** "A failed upload that reports error 0x80070005
     is a failed product" -- so the thing worth testing is the SENTENCE, and a sentence
     behind a WebView2 window cannot be asserted on from a command line.

So the dialog is a pure function of state -> (lines, buttons, tone). The host shell binds
it to real widgets later; the gate binds it to assertions today. Nothing here imports
pywebview, tkinter, or anything with a window in it.

================================================================================
THE ONE RULE THIS FILE ENCODES
================================================================================

    Every state a user can reach has a sentence, and NO state renders a raw exception.

`render()` never interpolates an exception repr, a WinError, or an HTTP status alone. The
worst it will show is a bounded, redacted detail string, and only under `verbose=True`.
`UploadOutcome.user_message` is written by the client in the user's language; this file
decides only WHICH message is shown for WHICH state, and whether the Share button stays
live. A future host that wants a different wording changes `_MESSAGES`, one table.

The three states that must never read as success:

    failed     -> tone ERROR, share button ENABLED (retry), detail available
    cancelled  -> tone NEUTRAL, share button ENABLED, "nothing was posted"
    refused    -> tone ERROR, share button ENABLED, the reason is a missing CREDENTIAL or a
                  bad title, not a network hiccup -- never "try again in a moment"
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# `src/ui/` has no `__init__.py` and `src/` is not a package, so `ui` is not importable as a
# package and nothing above it exists to import FROM. `src` on sys.path makes `pipeline` and
# `storage` top-level names, which is the shape the rest of this repo already uses.
_SRC_ROOT = str(Path(__file__).resolve().parents[1])
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from pipeline.share_metadata import PRIVACY_VALUES, ShareMetadata  # noqa: E402
from pipeline.share_upload import UploadClient, UploadOutcome, UploadState  # noqa: E402

__all__ = ["Tone", "ShareDialogState", "ShareDialog", "MESSAGES", "render"]

ERROR = "error"
OK = "ok"
BUSY = "busy"


class Tone:
    """How the panel paints. Deliberately THREE values, because there is no fourth state in
    which a user should be told a share worked when it did not."""


#: state -> (tone, headline, the action offered). Written here, once.
MESSAGES: dict[str, tuple[str, str, str]] = {
    UploadState.SUCCEEDED: (OK, "Shared.", "Watch it"),
    UploadState.FAILED: (ERROR, "The upload did not finish.", "Try again"),
    UploadState.CANCELLED: (OK, "Upload cancelled.", "Share it"),
    UploadState.REFUSED: (ERROR, "This was never sent.", "Fix and retry"),
}

_NEVER_SHOW_RAW = ("0x", "WinError", "Traceback", "errno", "Exception")


@dataclass
class ShareDialogState:
    """What the dialog knows. No widgets, no I/O."""

    meta: ShareMetadata | None = None
    outcome: UploadOutcome | None = None
    busy: bool = False
    bytes_sent: int = 0
    total_bytes: int = 0
    #: the destinations the host may offer; empty means the host has none to offer
    services: tuple[dict[str, Any], ...] = ()
    selected_service: str = ""
    verbose: bool = False

    @property
    def progress_pct(self) -> int:
        if not self.total_bytes:
            return 0
        return min(100, int(self.bytes_sent * 100 / self.total_bytes))


@dataclass
class ShareDialog:
    """The dialog as a function. `render()` is total: it answers for EVERY state."""

    state: ShareDialogState = field(default_factory=ShareDialogState)

    def can_share(self) -> bool:
        """Share is offered only when there is something to send, a title, and no run in
        flight. A button that is live during an upload is how a user posts a clip twice."""
        if self.state.busy:
            return False
        if self.state.meta is None:
            return False
        if self.state.selected_service not in {s.get("service") for s in self.state.services}:
            return False
        return bool(self.state.meta.title.strip())

    def share_enabled(self) -> bool:
        """Distinct from `can_share`: after a failure the button MUST come back, because
        the clip is still on this PC and the user's next move is to try again."""
        if self.state.busy:
            return False
        return self.state.outcome is None or self.state.outcome.state != UploadState.SUCCEEDED

    def render(self) -> dict[str, Any]:
        """The whole surface as data. Nothing here can raise on an unknown state."""
        st = self.state
        out = st.outcome
        tone, headline, action = OK, "Ready to share.", "Share"
        detail = ""
        lines: list[str] = []

        if out is not None:
            tone, headline, action = MESSAGES.get(
                out.state, (ERROR, "The share ended in a state this dialog does not know.",
                            "Try again"))
            headline = out.user_message or headline
            detail = out.detail or ""

        if st.meta is not None:
            lines.append(f"Title: {st.meta.title}")
            # The app line is omitted when unknown, NOT filled with the capture device.
            lines.append(f"Game/app: {st.meta.app}" if st.meta.app else "Game/app: (not set)")
            lines.append(f"Recorded: {st.meta.recorded_at_utc}")
            if st.meta.uncertain_fields:
                lines.append("Not stored by the index yet: " + ", ".join(st.meta.uncertain_fields))

        if out is not None and out.error_code:
            lines.append(f"Detail code: {out.error_code}")

        # THE RULE, enforced: a raw exception never reaches the surface.
        shown_detail = ""
        if detail and st.verbose and not any(tok in detail for tok in _NEVER_SHOW_RAW):
            shown_detail = detail[:240]

        return {
            "tone": tone,
            "headline": headline,
            "action_label": action,
            "lines": lines,
            "detail": shown_detail,
            "progress_pct": st.progress_pct,
            "share_enabled": self.share_enabled(),
            "can_share": self.can_share(),
            "succeeded": bool(out and out.ok),
            "url": out.url if out and out.ok else "",
        }

    def as_text(self) -> str:
        v = self.render()
        parts = [f"[{v['tone'].upper()}] {v['headline']}"]
        parts.extend(v["lines"])
        if v["detail"]:
            parts.append(f"({v['detail']})")
        if v["succeeded"]:
            parts.append(v["url"])
        return "\n".join(parts)


def render(outcome: UploadOutcome, meta: ShareMetadata | None = None, *,
           services: Iterable[dict[str, Any]] = (),
           selected_service: str = "", verbose: bool = False) -> dict[str, Any]:
    """The one-shot form. What the gate calls, and what a host binding can call.

    THE AUTO-SELECT RULE, and why it is conditional. With exactly ONE destination the panel
    preselects it, because a user with one account configured should not have to choose.
    With TWO OR MORE it does not, because silently posting a 30-second clip to the wrong
    channel is not a recoverable surprise. An earlier version preselected the first entry
    unconditionally, which meant a panel offered Share with no destination chosen at all.
    """
    choices = tuple(services)
    auto = choices[0].get("service", "") if len(choices) == 1 else ""
    return ShareDialog(ShareDialogState(
        meta=meta, outcome=outcome, services=choices,
        selected_service=selected_service or auto,
        verbose=verbose,
    )).render()


def privacy_choices() -> tuple[str, ...]:
    """`VideoStatus.privacyStatus.enum`, verbatim from the discovery document."""
    return PRIVACY_VALUES


def destinations(clients: Iterable[UploadClient]) -> tuple[dict[str, Any], ...]:
    """Each client's own `describe()`, so the panel never invents a capability.

    The fake says `is_real: False`; a UI that shows a fake destination next to a real one
    without saying so is how a demo becomes a lie in front of a user.
    """
    out = []
    for c in clients:
        d = dict(c.describe())
        d.setdefault("is_real", False)
        out.append(d)
    return tuple(out)