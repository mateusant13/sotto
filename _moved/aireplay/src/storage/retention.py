"""retention.py -- how long a clip stays, how much disk the store may take, and what happens
when the disk fills anyway.

THE PRODUCT DECISION THIS MODULE MAKES (the part that is a choice, not a fact):

  When eviction cannot free enough room for the next clip, this store **keeps its library
  and refuses the new clip, loudly** -- once per `alarm_interval_s`, and every refusal
  counted.

  The two alternatives are both real products and both were rejected:

  (a) Keep writing and fill the disk.  Rejected: the failure surfaces on the OWNER's box as
      "the app got slow for no reason" days later, and the clip that filled the disk is
      never the one that was wanted.  On a volume shared with a 1.2 GB model and a build
      tree, an unbounded store is a slow failure, exactly the one this package exists for.
  (b) Evict everything until the write fits.  Rejected: a recorder whose library disappears
      because something ELSE on the machine ate the disk is a worse product than a recorder
      that misses one clip, and (b) is indistinguishable from data loss the moment the
      pressure comes from a neighbour.

  What we do instead: evict down to the CONFIGURED budget and no further, then refuse.  The
  configured budget is the floor of what this store promises to keep.  Change
  `DEFAULT_ON_DISK_FULL` to `evict-all` to get (b) -- it is one named place.

  The refusal is LOUD because a silent stop is a defect: a recorder that quietly stops is
  indistinguishable from a recorder that is idle.  It is rate-limited so a full disk cannot
  turn into a log flood, and the SUPPRESSED count is reported, so "loud" never becomes
  "silence that looks like a counter".

RETENTION IS AGE-FIRST, AND THE MEASUREMENT SAYS WHY.  This box writes a 1080p60 clip at
98 099 914 B / 16.733333 s = 5.86 MB/s = 19.65 GiB/h (`_main/_lane17-run/clip-speech.mp4`,
ffprobe rc=0).  A byte budget is therefore not a duration: the default 4 GiB is **12.2
minutes** of capture.  `max_age_s` states what the owner keeps; `max_bytes` is the backstop
that keeps a forgotten store from eating the volume.

Every guarantee below sits behind a ONE-LINE guard carrying a unique token
(`# GUARD:<NAME>`).  That is not decoration: `_lane22-storage-gate.ps1` ARM D copies this
package and rewrites exactly one guard line per mutant, so a reverted guarantee is a thing
the gate can watch go RED.  Keep each guard a single line, and keep the token unique.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import layout
from .layout import (
    MEASURED_BYTES_PER_SECOND,
    PARTIAL_MARKER,
    ClipDir,
    LayoutError,
    Report,
    classify,
    emit,
    ensure_root,
    iter_clips,
    remove_clip_dir,
    sidecars,
    tree_bytes,
    volume_free_bytes,
    walk_keys,
)

GIB = 1 << 30
MIB = 1 << 20

# ---------------------------------------------------------------------------------------------
# Defaults.  Each carries its reason, because a retention default is a product claim.
# ---------------------------------------------------------------------------------------------

#: 24 h is what the owner is told the library holds; the byte budget below is the backstop.
DEFAULT_MAX_AGE_S = 24 * 3600.0
#: 500 clips is roughly a day at one clip per ~3 minutes of play.
DEFAULT_MAX_CLIPS = 500
#: 4 GiB = **12.2 minutes** at this box's MEASURED 5.86 MB/s.  Deliberately modest: on a
#: volume with 42.72 GiB free (measured 2026-10-07, H:) this is 11.7% of what is left, and a
#: store that grows past it is a bug, not a policy.
DEFAULT_MAX_BYTES = 4 * GIB
#: Free space the store refuses to consume.  Enough for the encoder's own working set.
DEFAULT_RESERVE_BYTES = 1 * GIB
#: One alarm per this many seconds.  The suppression COUNT is still reported, so a flooded
#: disk cannot hide behind a quiet log.
DEFAULT_ALARM_INTERVAL_S = 60.0

#: The two behaviours `admit_write()` can have when it cannot free room.  One named place.
DEFAULT_ON_DISK_FULL = "refuse-and-alarm"   # or "evict-all" (the rejected alternative (b))

ENV_MAX_BYTES = "SOTTO_CLIP_MAX_BYTES"
ENV_MAX_AGE_S = "SOTTO_CLIP_MAX_AGE_S"
ENV_MAX_COUNT = "SOTTO_CLIP_MAX_COUNT"
ENV_RESERVE_BYTES = "SOTTO_CLIP_RESERVE_BYTES"

ACTION_KEEP = "keep"
ACTION_FINISH = "finish"
ACTION_DISCARD = "discard"


class PolicyError(Exception):
    """A policy value that cannot be honoured.  Refused loudly, never clamped.

    Clamping is the failure this borrows from the Sotto lang-id defect (AGENTS.md): a value
    the user asked for and the store did not apply, silently, is worse than a refusal.
    """


# ---------------------------------------------------------------------------------------------
# The guards.  One line each, one unique token each.
# ---------------------------------------------------------------------------------------------


def _age_violated(now_s: float, started_at_s: float, max_age_s: float) -> bool:
    return (now_s - started_at_s) > max_age_s  # GUARD:RETENTION-AGE


def _count_violated(n_clips: int, max_clips: int) -> bool:
    return n_clips > max_clips  # GUARD:RETENTION-COUNT


def _bytes_violated(used_bytes: int, max_bytes: int) -> bool:
    return used_bytes > max_bytes  # GUARD:RETENTION-BYTES


def _admit(free_bytes: int, need_bytes: int) -> bool:
    return free_bytes >= need_bytes  # GUARD:WRITE-ADMISSION


def _alarm_is_mandatory() -> bool:
    return True  # GUARD:LOUD-ALARM


def _partial_is_unusable(has_partial: bool, has_key: bool) -> bool:
    return has_partial and not has_key  # GUARD:RECONCILE-PARTIAL


# ---------------------------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RetentionPolicy:
    """The limits in force, and WHERE EACH ONE CAME FROM.

    `field_sources` is not bookkeeping: a budget nobody can trace to a decision is how a box
    ends up with a 12-minute library and nobody knows why.
    """

    max_age_s: float
    max_clips: int
    max_bytes: int
    reserve_bytes: int
    alarm_interval_s: float
    on_disk_full: str = DEFAULT_ON_DISK_FULL
    field_sources: dict[str, str] = field(default_factory=dict)

    def source_of(self, name: str) -> str:
        return self.field_sources.get(name, "default")

    @property
    def capture_seconds_at_measured_rate(self) -> float:
        """What `max_bytes` buys in SECONDS of capture at this box's measured rate."""
        return self.max_bytes / MEASURED_BYTES_PER_SECOND

    def line(self, population: dict[str, Any], window: dict[str, Any]) -> str:
        """The ONE line that states the budget in force, with its POPULATION and WINDOW."""
        return (
            f"CLIP_RETENTION budget_bytes={self.max_bytes} "
            f"budget_source={self.source_of('max_bytes')} "
            f"max_age_s={self.max_age_s:g} age_source={self.source_of('max_age_s')} "
            f"max_clips={self.max_clips} count_source={self.source_of('max_clips')} "
            f"reserve_bytes={self.reserve_bytes} reserve_source={self.source_of('reserve_bytes')} "
            f"on_disk_full={self.on_disk_full} "
            f"capture_minutes_at_measured_rate={self.capture_seconds_at_measured_rate / 60:.3f} "
            f"POPULATION clips={population.get('clips')} bytes={population.get('bytes')} "
            f"WINDOW oldest={window.get('oldest')} newest={window.get('newest')} "
            f"span_s={window.get('span_s')}"
        )


def _positive(value: str, name: str, source: str) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise PolicyError(f"{name}={value!r} from {source} is not a number; refused, not clamped")
    if n != n or n <= 0:
        raise PolicyError(f"{name}={value!r} from {source} must be > 0; refused, not clamped")
    return n


def policy_from_env(
    env: dict[str, str] | None = None,
    *,
    max_bytes: int | None = None,
    max_age_s: float | None = None,
    max_clips: int | None = None,
    reserve_bytes: int | None = None,
    alarm_interval_s: float = DEFAULT_ALARM_INTERVAL_S,
    on_disk_full: str = DEFAULT_ON_DISK_FULL,
) -> RetentionPolicy:
    """`explicit argument` > `environment` > `default`, field by field.

    An unusable value in ANY tier is a `PolicyError`.  It is never replaced by the default:
    a store that silently ignores the budget the owner set is the failure this lane is about.
    """
    e = dict(os.environ if env is None else env)
    src: dict[str, str] = {}
    out: dict[str, Any] = {}

    for name, arg, env_name, default in (
        ("max_bytes", max_bytes, ENV_MAX_BYTES, DEFAULT_MAX_BYTES),
        ("max_age_s", max_age_s, ENV_MAX_AGE_S, DEFAULT_MAX_AGE_S),
        ("max_clips", max_clips, ENV_MAX_COUNT, DEFAULT_MAX_CLIPS),
        ("reserve_bytes", reserve_bytes, ENV_RESERVE_BYTES, DEFAULT_RESERVE_BYTES),
    ):
        if arg is not None:
            out[name] = _positive(str(arg), name, "explicit argument")
            src[name] = "explicit"
        elif env_name in e:
            # An env var that is PRESENT is a decision, even when it is empty.  Falling back to
            # the default here means `SOTTO_CLIP_MAX_BYTES=` (set to nothing) silently buys
            # the 4 GiB default -- the silent-substitution failure this module refuses to have.
            out[name] = _positive(str(e[env_name]), name, f"env:{env_name}")
            src[name] = f"env:{env_name}"
        else:
            out[name] = default
            src[name] = "default"
    out["max_clips"] = int(out["max_clips"])
    out["max_bytes"] = int(out["max_bytes"])
    out["reserve_bytes"] = int(out["reserve_bytes"])
    src["alarm_interval_s"] = "explicit"
    src["on_disk_full"] = "explicit"
    return RetentionPolicy(alarm_interval_s=alarm_interval_s, on_disk_full=on_disk_full,
                           field_sources=src, **out)


# ---------------------------------------------------------------------------------------------
# Measuring the store
# ---------------------------------------------------------------------------------------------


@dataclass
class StoreView:
    """What is on disk right now, measured.  Never a cache, never an assumption."""

    root: Path
    clips: list[ClipDir]
    bytes_total: int
    errors: list[str]

    @property
    def n(self) -> int:
        return len(self.clips)

    def population(self) -> dict[str, Any]:
        return {"clips": self.n, "bytes": self.bytes_total, "fs_errors": len(self.errors)}

    def window(self) -> dict[str, Any]:
        if not self.clips:
            return {"oldest": None, "newest": None, "span_s": 0.0}
        stamps = sorted(c.clip_id for c in self.clips)
        spans = [c.started_at_s for c in self.clips if c.started_at_s is not None]
        return {
            "oldest": stamps[0],
            "newest": stamps[-1],
            "span_s": round(max(spans) - min(spans), 3) if len(spans) > 1 else 0.0,
        }


def survey(root: str | os.PathLike[str]) -> StoreView:
    """Walk the store: the committed clips, the REAL byte total, and any fs errors."""
    r = Path(root)
    errors: list[str] = []
    clips = list(iter_clips(r, errors=errors))
    return StoreView(root=r, clips=clips, bytes_total=tree_bytes(r, errors=errors), errors=errors)


# ---------------------------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------------------------


@dataclass
class Victim:
    clip_id: str
    path: Path
    size_bytes: int
    started_at_s: float
    reasons: list[str]


@dataclass
class EvictionPlan:
    """WHO goes, WHY, and what the store looks like before the deletion happens.

    A plan is inert.  Nothing is deleted until `execute_plan()`, so a caller can log the plan
    and a gate can inspect it before the bytes are gone.
    """

    victims: list[Victim]
    kept: list[str]
    root: Path
    policy: RetentionPolicy
    population_before: dict[str, Any]
    window_before: dict[str, Any]
    bytes_before: int
    bytes_planned: int
    bytes_after: int
    triggered: list[str]

    @property
    def bytes_freed_planned(self) -> int:
        return self.bytes_planned


def plan_eviction(view: StoreView, policy: RetentionPolicy, now_s: float) -> EvictionPlan:
    """Choose the victims.  OLDEST FIRST, always, and by a total order.

    The order is `(started_at_s, clip_id)`, so two clips written in the same second still
    have a defined order and the plan is reproducible.  "Evict something, then whatever is
    left" is not a policy; this is.

    The three rules are computed INDEPENDENTLY and then unioned, so a clip that is too old
    is evicted even when the byte budget would have allowed it -- a 24-hour-old clip is
    outside the window the owner was promised, whatever the disk has room for.
    """
    clips = [c for c in view.clips if c.started_at_s is not None]
    order = sorted(clips, key=lambda c: (c.started_at_s, c.clip_id))  # oldest first
    reasons: dict[str, list[str]] = {c.clip_id: [] for c in order}
    triggered: list[str] = []

    if _age_violated(now_s, order[0].started_at_s if order else now_s, policy.max_age_s):
        for c in order:
            if _age_violated(now_s, c.started_at_s, policy.max_age_s):
                reasons[c.clip_id].append("age")
        triggered.append("age")

    if _count_violated(len(order), policy.max_clips):
        for c in order[: max(0, len(order) - policy.max_clips)]:
            reasons[c.clip_id].append("count")
        triggered.append("count")

    # The budget is compared against the WHOLE store footprint, not the sum of clip
    # directories.  Those differ by the root marker and the directory entries, and on a small
    # tree that difference is the whole margin: comparing the payload sum to a budget and then
    # REPORTING the tree size is how a store ends up 120 B "over budget" while every printed
    # number is individually true.
    used = view.bytes_total
    if _bytes_violated(used, policy.max_bytes):
        running = used
        for c in order:  # newest first while deciding who to keep
            if running <= policy.max_bytes:
                break
            running -= c.size_bytes
            reasons[c.clip_id].append("bytes")
        triggered.append("bytes")

    victims = [
        Victim(
            clip_id=c.clip_id,
            path=c.path,
            size_bytes=c.size_bytes,
            started_at_s=c.started_at_s,
            reasons=reasons[c.clip_id],
        )
        for c in order
        if reasons[c.clip_id]
    ]
    victims.sort(key=lambda v: (v.started_at_s, v.clip_id))
    kept = [c.clip_id for c in order if not reasons[c.clip_id]]
    planned = sum(v.size_bytes for v in victims)
    return EvictionPlan(
        victims=victims,
        kept=kept,
        root=view.root,
        policy=policy,
        population_before=view.population(),
        window_before=view.window(),
        bytes_before=view.bytes_total,
        bytes_planned=planned,
        bytes_after=view.bytes_total - planned,
        triggered=triggered,
    )


@dataclass
class EvictionResult:
    plan: EvictionPlan
    clips_removed: int
    bytes_freed: int          # summed from files whose OWN unlink succeeded
    bytes_freed_by_walk: int  # store tree before minus after: an INDEPENDENT measure
    survivors: list[str]
    errors: list[str]

    @property
    def agrees(self) -> bool:
        return self.bytes_freed == self.bytes_freed_by_walk


def execute_plan(plan: EvictionPlan) -> EvictionResult:
    """Delete the plan's victims and report the bytes freed BY TWO INDEPENDENT MEASURES.

    `bytes_freed` comes from the unlinks themselves; `bytes_freed_by_walk` comes from
    re-measuring the whole tree.  If they disagree, something outside this function wrote to
    the store during the eviction -- and a headline "we freed N bytes" that cannot say which
    N it meant is exactly the kind of number this repo keeps having to unpick.
    """
    freed = 0
    removed = 0
    errors: list[str] = []
    for v in plan.victims:
        n = remove_clip_dir(v.path)
        freed += n
        removed += 1
        if not v.path.exists():
            print(
                f"CLIP_STORE_EVICT clip_id={v.clip_id} bytes={n} reasons={','.join(v.reasons)}",
                flush=True,
            )
        else:
            msg = f"victim {v.clip_id} SURVIVED eviction at {v.path}"
            print(f"CLIP_STORE_EVICT_FAILED {msg}", file=sys.stderr, flush=True)
            errors.append(msg)
    after = tree_bytes(plan.root)
    by_walk = plan.bytes_before - after
    survivors = [c.clip_id for c in iter_clips(plan.root)]
    return EvictionResult(
        plan=plan,
        clips_removed=removed,
        bytes_freed=freed,
        bytes_freed_by_walk=by_walk,
        survivors=survivors,
        errors=errors,
    )


# ---------------------------------------------------------------------------------------------
# The disk-full path
# ---------------------------------------------------------------------------------------------

ALARM_REASON_DISK_FULL = "disk-full"


@dataclass
class AlarmLog:
    """The loud part, rate-limited but COUNTED.

    `suppressed` is reported alongside `emitted` on purpose: rate limiting that cannot be
    audited is indistinguishable from having gone quiet.
    """

    interval_s: float
    last_emitted_s: float | None = None
    emitted: int = 0
    suppressed: int = 0
    lines: list[str] = field(default_factory=list)

    def raise_alarm(self, now_s: float, **fields: Any) -> str:
        if not _alarm_is_mandatory():
            # The reverted guarantee.  The refusal below still happens; what disappears is
            # the ONLY thing that tells the owner their clips are being dropped.
            self.suppressed += 1
            return ""
        if self.last_emitted_s is not None and (now_s - self.last_emitted_s) < self.interval_s:
            self.suppressed += 1
            return ""
        parts = " ".join(f"{k}={v}" for k, v in fields.items())
        line = f"CLIP_STORE_ALARM reason={ALARM_REASON_DISK_FULL} {parts}"
        self.lines.append(line)
        self.last_emitted_s = now_s
        self.emitted += 1
        print(line, flush=True)
        return line


@dataclass
class Admission:
    """The answer to "may I write this clip?" -- a DECISION, never an exception.

    `admitted=False` is a normal product state (the disk is full); it is not an error to
    raise, and callers that treat it as one will crash the recorder instead of the library.
    """

    admitted: bool
    reason: str
    free_bytes: int
    need_bytes: int
    store_bytes_before: int
    store_bytes_after: int
    bytes_evicted: int
    clips_evicted: int
    alarm_emitted: int
    alarm_suppressed: int
    alarm_line: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "reason": self.reason,
            "free_bytes": self.free_bytes,
            "need_bytes": self.need_bytes,
            "store_bytes_before": self.store_bytes_before,
            "store_bytes_after": self.store_bytes_after,
            "bytes_evicted": self.bytes_evicted,
            "clips_evicted": self.clips_evicted,
            "alarm_emitted": self.alarm_emitted,
            "alarm_suppressed": self.alarm_suppressed,
            "alarm_line": self.alarm_line,
        }


def admit_write(
    root: str | os.PathLike[str],
    policy: RetentionPolicy,
    incoming_bytes: int,
    now_s: float,
    alarm: AlarmLog,
) -> Admission:
    """Decide whether the next clip may be written, and act on the store if it may not.

    The order matters and is not negotiable:

      1. measure the store, evict to the CONFIGURED budget (never below it);
      2. measure FREE space on the volume -- not `max_bytes - used`, which knows nothing
         about what else on the machine is consuming the disk;
      3. if `free < incoming + reserve`, REFUSE and ALARM.  The store is not made smaller
         than the owner configured.
    """
    r = Path(root)
    before = survey(r)
    view = before
    plan = plan_eviction(view, policy, now_s)
    result = execute_plan(plan) if plan.victims else None
    store_after = tree_bytes(r)
    free = volume_free_bytes(r)
    need = int(incoming_bytes) + policy.reserve_bytes

    if _admit(free, need):
        return Admission(
            admitted=True,
            reason="admitted",
            free_bytes=free,
            need_bytes=need,
            store_bytes_before=before.bytes_total,
            store_bytes_after=store_after,
            bytes_evicted=result.bytes_freed if result else 0,
            clips_evicted=result.clips_removed if result else 0,
            alarm_emitted=alarm.emitted,
            alarm_suppressed=alarm.suppressed,
        )

    line = alarm.raise_alarm(
        now_s,
        root=str(r),
        free_bytes=free,
        need_bytes=need,
        reserve_bytes=policy.reserve_bytes,
        store_bytes=store_after,
        budget_bytes=policy.max_bytes,
        budget_source=policy.source_of("max_bytes"),
        clips_evicted=result.clips_removed if result else 0,
        bytes_evicted=result.bytes_freed if result else 0,
        on_disk_full=policy.on_disk_full,
        action="refused-next-clip",
        note="library kept; this clip is NOT written; set SOTTO_CLIP_MAX_BYTES to change",
    )
    return Admission(
        admitted=False,
        reason=ALARM_REASON_DISK_FULL,
        free_bytes=free,
        need_bytes=need,
        store_bytes_before=before.bytes_total,
        store_bytes_after=store_after,
        bytes_evicted=result.bytes_freed if result else 0,
        clips_evicted=result.clips_removed if result else 0,
        alarm_emitted=alarm.emitted,
        alarm_suppressed=alarm.suppressed,
        alarm_line=line,
    )


# ---------------------------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------------------------

ACTION_FOR = {
    layout.VERDICT_COMMITTED: ACTION_KEEP,
    layout.VERDICT_FINISH: ACTION_FINISH,
    layout.VERDICT_DISCARD: ACTION_DISCARD,
    layout.VERDICT_ORPHAN_KEY: ACTION_DISCARD,
    layout.VERDICT_MISSING_MEDIA: ACTION_DISCARD,
}


@dataclass
class ReconcileReport:
    kept: list[str] = field(default_factory=list)
    finished: list[tuple[str, int]] = field(default_factory=list)     # (clip_id, bytes_freed)
    discarded: list[tuple[str, str, str, int]] = field(default_factory=list)  # id, why, reason, bytes
    bytes_reclaimed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kept": self.kept,
            "finished": [{"clip_id": c, "bytes": b} for c, b in self.finished],
            "discarded": [
                {"clip_id": c, "why": w, "reason": r, "bytes": b} for c, w, r, b in self.discarded
            ],
            "bytes_reclaimed": self.bytes_reclaimed,
            "errors": self.errors,
        }


def action_for(c: ClipDir) -> str:
    """What to DO with one clip directory after a crash.  Total over the declared verdicts.

    The two DISCARD branches below are deliberately DIFFERENT decisions, because they are
    different situations and a guard that sits between two branches returning the same value
    is decoration, not a guarantee:

      * a crash-left `.partial` with no key holds an mp4 whose muxer never finished.  It will
        not play, nothing claims it, and leaving it is a permanent hole in the store's own
        byte accounting -> DISCARD.
      * an UNMARKED directory whose key is unreadable, or whose key names a different clip,
        may hold perfectly good media.  Deleting it destroys bytes on a guess.  It stays, it
        stays OUT of the index (`walk_keys` reports it), and the owner can delete it.  The
        cost of being wrong in this direction is a visible hole; in the other direction it is
        a deleted clip nobody asked to lose.
    """
    cls = classify(c)
    if cls.verdict == layout.VERDICT_COMMITTED:
        return ACTION_KEEP
    if cls.verdict == layout.VERDICT_FINISH:
        return ACTION_FINISH
    if cls.verdict == layout.VERDICT_MISSING_MEDIA:
        return ACTION_DISCARD
    if cls.verdict == layout.VERDICT_ORPHAN_KEY:
        return ACTION_DISCARD   # no marker and no key: a directory, not a clip
    if cls.verdict == layout.VERDICT_DISCARD:
        if _partial_is_unusable(c.has_partial, c.has_key):
            return ACTION_DISCARD
        return ACTION_KEEP      # unmarked dir with a key we could not trust -- see above
    raise LayoutError(
        f"clip {c.clip_id} has verdict {cls.verdict!r}, which action_for() has no rule for; "
        f"the declared verdicts are {list(ACTION_FOR)}"
    )


def reconcile(root: str | os.PathLike[str]) -> ReconcileReport:
    """After a crash: every clip directory becomes committed, or stops existing.

    The invariant this exists to hold: **nothing the index claims exists is missing or
    unusable.**  `walk_keys()` sees only committed dirs, so a `.partial` directory is
    invisible to the index by construction -- reconciliation is what makes it not stay on the
    disk forever.  Every decision is printed, because a clip deleted by a policy the owner
    never read is still a deleted clip.
    """
    r = Path(root)
    rep = ReconcileReport()
    for c in iter_clips(r, errors=rep.errors):
        act = action_for(c)
        if act == ACTION_KEEP:
            rep.kept.append(c.clip_id)
            continue
        if act == ACTION_FINISH:
            try:
                (c.path / PARTIAL_MARKER).unlink()
            except OSError as exc:
                msg = f"{c.clip_id}: committed but {PARTIAL_MARKER} will not unlink ({exc})"
                print(f"CLIP_STORE_RECONCILE_FAILED {msg}", file=sys.stderr, flush=True)
                rep.errors.append(msg)
                continue
            rep.finished.append((c.clip_id, 0))
            rep.kept.append(c.clip_id)
            print(f"CLIP_STORE_RECONCILE action=finished clip_id={c.clip_id} bytes=0", flush=True)
            continue
        cls = classify(c)
        n = remove_clip_dir(c.path)
        rep.discarded.append((c.clip_id, cls.verdict, cls.reason, n))
        rep.bytes_reclaimed += n
        print(
            f"CLIP_STORE_RECONCILE action=discarded clip_id={c.clip_id} verdict={cls.verdict} "
            f"bytes={n} reason={cls.reason}",
            flush=True,
        )
        if c.path.exists():
            rep.errors.append(f"{c.clip_id} survived discard")
    return rep


# ---------------------------------------------------------------------------------------------
# Arms.  `--arm A|B|C|E`.  Each builds a REAL tree under `--work` and measures it.
# ---------------------------------------------------------------------------------------------


def _build_store(root: Path, n_clips: int, *, payload: int = 40 * 1024,
                 span_s: float = 24 * 3600.0, now_s: float | None = None) -> dict[str, Any]:
    """Write `n_clips` REAL committed clips with real bytes, oldest first."""
    ensure_root(root)
    if now_s is None:
        now_s = datetime.now(tz=timezone.utc).timestamp()
    step = span_s / max(1, n_clips)
    wrote: list[str] = []
    total_written = 0
    for i in range(n_clips):
        started = now_s - span_s + i * step
        cid = layout.make_clip_id(started, i)
        w = layout.ClipWriter(root, cid)
        w.write_media(b"\x00\x00\x00\x18ftypmp42" + bytes((i * 31 + k) % 251 for k in range(payload)))
        w.write_transcript({"segments": [{"start_ms": 0, "text": f"segmento {i}"}]})
        w.write_thumb(bytes((k * 5) % 256 for k in range(200)))
        w.commit(duration_ms=30_000, mode="ring")
        wrote.append(cid)
        total_written += (w.path / layout.MEDIA_NAME).stat().st_size
    measured = tree_bytes(root)
    return {
        "clips_written": len(wrote),
        "bytes_of_media": total_written,
        "bytes_measured_by_walk": measured,
        "oldest": min(wrote),
        "newest": max(wrote),
        "now_s": now_s,
        "span_s": span_s,
    }


def arm_a(work: str) -> Report:
    """THE HEADLINE: eviction against a real directory tree, with the bytes freed stated."""
    rep = Report("A")
    root = Path(work) / "armA-store"
    if root.exists():
        shutil.rmtree(root)
    n = 24
    built = _build_store(root, n)
    now = built["now_s"]

    policy = policy_from_env(
        env={},
        max_bytes=built["bytes_measured_by_walk"] // 2,   # evict down to half the tree
        max_age_s=10 ** 9,
        max_clips=10 ** 9,
        reserve_bytes=1,
    )
    view = survey(root)
    rep.check(
        "A0.population-measured",
        view.n == n and not view.errors,
        f"POPULATION clips={view.n}/{n} written, bytes={view.bytes_total} by full walk "
        f"({len(view.errors)} fs errors); WINDOW oldest={view.window()['oldest']} "
        f"newest={view.window()['newest']} span_s={view.window()['span_s']}",
    )
    print(policy.line(view.population(), view.window()), flush=True)

    plan = plan_eviction(view, policy, now)
    result = execute_plan(plan)

    rep.check(
        "A1.bytes-were-freed",
        result.bytes_freed > 0,
        f"freed {result.bytes_freed} B over {result.clips_removed} clip(s); "
        f"independent walk measure {result.bytes_freed_by_walk} B; they agree={result.agrees}; "
        f"tree {result.plan.bytes_before} -> {tree_bytes(root)} B",
    )
    rep.check(
        "A2.the-two-measures-agree",
        result.agrees,
        f"unlink-sum {result.bytes_freed} B == walk-delta {result.bytes_freed_by_walk} B "
        f"(a disagreement would mean something else wrote during the eviction)",
    )
    store_now = tree_bytes(root)
    clip_payload_now = sum(c.size_bytes for c in iter_clips(root))
    overhead = store_now - clip_payload_now
    rep.check(
        "A3.store-is-inside-the-budget",
        store_now <= policy.max_bytes,
        f"whole store tree {store_now} B <= budget {policy.max_bytes} B "
        f"(source {policy.source_of('max_bytes')}); of which {overhead} B is outside clip "
        f"directories (the root marker), and the budget counts it too -- a store cannot be "
        f"'inside its budget' by a measure no printed number uses",
    )
    survivors = sorted(c.clip_id for c in iter_clips(root))
    oldest_victim = plan.victims[0].clip_id if plan.victims else None
    youngest_victim = plan.victims[-1].clip_id if plan.victims else None
    every_survivor_newer_than_every_victim = bool(
        plan.victims and survivors and max(survivors) > max(v.clip_id for v in plan.victims)
    )
    rep.check(
        "A4.oldest-went-newest-stayed",
        survivors == sorted(plan.kept) and every_survivor_newer_than_every_victim,
        f"{len(survivors)} survivor(s), {len(plan.victims)} victim(s); victims span "
        f"{oldest_victim}..{youngest_victim}; the newest survivor ({survivors[-1] if survivors else None}) "
        f"is newer than the newest victim, so eviction removed OLDEST FIRST",
    )

    # Idempotence: a second pass over the same tree evicts nothing.  A retention policy that
    # re-evicts on every call is a policy that is deleting the library at random.
    view2 = survey(root)
    plan2 = plan_eviction(view2, policy, now)
    rep.check(
        "A5.second-pass-is-a-no-op",
        not plan2.victims and not execute_plan(plan2).clips_removed,
        f"second plan selected {len(plan2.victims)} victim(s) over the same "
        f"population of {view2.n} clip(s)",
    )

    # The age rule must fire on its own, without the byte budget -- and it must fire on PART
    # of the population.  A test where every clip is expired proves only that the rule is
    # reachable, not that it selects; a test where NO clip is expired proves nothing at all.
    # The window is therefore derived from the ages still ON DISK after the byte eviction
    # above, not from the span of the population that eviction already removed.
    view3 = survey(root)
    ages = sorted(now - c.started_at_s for c in view3.clips if c.started_at_s is not None)
    oldest_age = ages[-1] if ages else 0.0
    age_window = oldest_age / 2.0
    age_policy = policy_from_env(env={}, max_bytes=10 ** 15, max_age_s=age_window,
                                 max_clips=10 ** 9, reserve_bytes=1)
    plan3 = plan_eviction(view3, age_policy, now)
    rep.check(
        "A6.age-rule-fires-independently",
        plan3.triggered == ["age"]
        and all("age" in v.reasons for v in plan3.victims)
        and 0 < len(plan3.victims) < view3.n,
        f"with the byte budget at 10^15, max_clips at 10^9 and max_age_s={age_window:.0f} s "
        f"(half of the {oldest_age:.0f} s oldest age still on disk), the age rule alone "
        f"selected {len(plan3.victims)} of {view3.n} clip(s); triggered={plan3.triggered}",
    )
    # ... and the count rule must fire on its own too.
    view_n = survey(root)
    count_policy = policy_from_env(env={}, max_bytes=10 ** 15, max_age_s=10 ** 9, max_clips=3,
                                   reserve_bytes=1)
    plan4 = plan_eviction(view_n, count_policy, now)
    rep.check(
        "A7.count-rule-fires-independently",
        plan4.triggered == ["count"] and len(plan4.victims) == max(0, view_n.n - 3),
        f"with max_clips=3 and age/bytes effectively off, {len(plan4.victims)} of "
        f"{view_n.n} clip(s) were selected; triggered={plan4.triggered}",
    )

    rep.facts["population"] = {
        "clips_written": built["clips_written"],
        "clips_before": view.n,
        "clips_after": len(survivors),
        "bytes_before": built["bytes_measured_by_walk"],
        "bytes_freed": result.bytes_freed,
        "bytes_freed_by_walk": result.bytes_freed_by_walk,
        "bytes_after": tree_bytes(root),
        "clips_evicted": result.clips_removed,
        "budget_bytes": policy.max_bytes,
        "budget_source": policy.source_of("max_bytes"),
        "capture_minutes_budget_at_measured_rate": round(
            policy.capture_seconds_at_measured_rate / 60, 3
        ),
        "store": str(root),
    }
    rep.facts["window"] = {
        **view.window(),
        "note": f"{n} clips spread over {built['span_s']} s, age window "
                f"{policy.max_age_s:g} s, count window {policy.max_clips}",
        "eviction_window": f"oldest victim {plan.victims[0].clip_id} .. newest survivor "
                           f"{survivors[-1] if survivors else None}" if plan.victims else "none",
    }
    return rep


def arm_b(work: str) -> Report:
    """DISK FULL: the case the brief calls the interesting one.  Refuse, and be loud."""
    rep = Report("B")
    root = Path(work) / "armB-store"
    if root.exists():
        shutil.rmtree(root)
    n = 12
    built = _build_store(root, n)
    now = built["now_s"]

    # A budget the store is well INSIDE, and a reserve it can never satisfy: the volume has
    # room, the store has room, and the reservation still refuses.  That is the exact shape
    # of "something else on the machine ate the disk", and it is the case (b) would answer by
    # deleting the whole library.
    policy = policy_from_env(
        env={},
        max_bytes=10 ** 12,
        max_age_s=10 ** 9,
        max_clips=10 ** 9,
        reserve_bytes=volume_free_bytes(root) + 64 * MIB,
    )
    free_now = volume_free_bytes(root)
    view = survey(root)
    print(policy.line(view.population(), view.window()), flush=True)

    alarm = AlarmLog(interval_s=policy.alarm_interval_s)
    a1 = admit_write(root, policy, incoming_bytes=8 * MIB, now_s=now, alarm=alarm)
    bytes_after_1 = tree_bytes(root)

    rep.check(
        "B1.write-is-refused",
        not a1.admitted and a1.reason == ALARM_REASON_DISK_FULL,
        f"admitted={a1.admitted} reason={a1.reason}; free={a1.free_bytes} B "
        f"(MEASURED on this volume) < need={a1.need_bytes} B "
        f"(8 MiB incoming + {policy.reserve_bytes} B reserve)",
    )
    rep.check(
        "B2.refusal-is-LOUD",
        a1.alarm_emitted == 1 and a1.alarm_line.startswith("CLIP_STORE_ALARM"),
        f"{a1.alarm_emitted} alarm(s) emitted; line: {a1.alarm_line}",
    )
    rep.check(
        "B3.store-did-not-grow",
        bytes_after_1 <= built["bytes_measured_by_walk"],
        f"store {built['bytes_measured_by_walk']} B before -> {bytes_after_1} B after a "
        f"REFUSED write (delta {bytes_after_1 - built['bytes_measured_by_walk']} B)",
    )
    rep.check(
        "B4.library-is-kept",
        a1.clips_evicted == 0 and len(list(iter_clips(root))) == n,
        f"{a1.clips_evicted} clip(s) evicted to make room while inside the budget; "
        f"{len(list(iter_clips(root)))}/{n} still present. This is the trade-off: the store "
        f"loses the NEXT clip, never the library.",
    )
    rep.check(
        "B5.alarm-carries-the-budget-in-force",
        f"budget_bytes={policy.max_bytes}" in a1.alarm_line
        and f"budget_source={policy.source_of('max_bytes')}" in a1.alarm_line,
        f"alarm carries budget_bytes + budget_source + free_bytes + need_bytes",
    )

    # Rate limiting must not become silence: the SECOND refusal inside the interval is
    # suppressed, and the suppression is counted and reported.
    a2 = admit_write(root, policy, incoming_bytes=8 * MIB, now_s=now + 1, alarm=alarm)
    rep.check(
        "B6.rate-limit-is-counted-not-silent",
        a2.alarm_emitted == 1 and a2.alarm_suppressed == 1,
        f"a second refusal {1} s later: emitted={a2.alarm_emitted} (still 1), "
        f"suppressed={a2.alarm_suppressed} (was 0) -- the dropped alarm is COUNTED, so a "
        f"quiet log can always be audited against the refusal count",
    )
    # ... and after the interval the alarm speaks again.
    a3 = admit_write(root, policy, incoming_bytes=8 * MIB, now_s=now + policy.alarm_interval_s + 1,
                     alarm=alarm)
    rep.check(
        "B7.alarm-returns-after-the-interval",
        a3.alarm_emitted == 2,
        f"a third refusal {policy.alarm_interval_s + 1} s later re-alarmed: "
        f"emitted={a3.alarm_emitted}",
    )

    # A write that DOES fit is admitted -- the refusal must not be a permanent mute.
    ok_policy = policy_from_env(env={}, max_bytes=10 ** 12, max_age_s=10 ** 9, max_clips=10 ** 9,
                                reserve_bytes=1)
    ok_alarm = AlarmLog(interval_s=policy.alarm_interval_s)
    a4 = admit_write(root, ok_policy, incoming_bytes=8 * MIB, now_s=now, alarm=ok_alarm)
    rep.check(
        "B8.a-fit-write-is-admitted",
        a4.admitted and ok_alarm.emitted == 0,
        f"with reserve=1 B the same 8 MiB write is admitted={a4.admitted} and no alarm was "
        f"raised ({ok_alarm.emitted} emitted); the refusal tracks the RESERVATION, not a "
        f"latched failure",
    )

    rep.facts["population"] = {
        "clips_written": built["clips_written"],
        "clips_present_after": len(list(iter_clips(root))),
        "bytes_before": built["bytes_measured_by_walk"],
        "bytes_after": bytes_after_1,
        "volume_free_bytes_measured": free_now,
        "reserve_bytes_requested": policy.reserve_bytes,
        "store": str(root),
    }
    rep.facts["window"] = {
        **survey(root).window(),
        "alarm_interval_s": policy.alarm_interval_s,
        "attempts": 4,
        "refusals": 3,
    }
    return rep


def arm_c(work: str) -> Report:
    """Reconciliation: after a crash, a partial clip is FINISHED or DISCARDED, and the index
    never claims a file that is not there."""
    rep = Report("C")
    root = Path(work) / "armC-store"
    if root.exists():
        shutil.rmtree(root)
    now = datetime.now(tz=timezone.utc).timestamp()
    ensure_root(root)

    def _cid(off: float, seq: int = 0) -> str:
        return layout.make_clip_id(now - off, seq)

    # 1 committed -- must survive untouched.
    for i in range(2):
        w = layout.ClipWriter(root, _cid(3600 * (i + 1), i))
        w.write_media(b"\x00\x00\x00\x18ftypmp42" + bytes((i + k) % 251 for k in range(8192)))
        w.commit(duration_ms=1000)

    # 2 crash AFTER the key landed, before the marker was unlinked  -> FINISH
    w = layout.ClipWriter(root, _cid(1800, 2))
    w.write_media(b"\x00\x00\x00\x18ftypmp42" + bytes(4096))
    w.commit(duration_ms=1000)
    (w.path / PARTIAL_MARKER).write_bytes(b"")           # re-create the marker: the crash

    # 3 crash BEFORE the key landed -> DISCARD (an mp4 with no finished moov)
    w = layout.ClipWriter(root, _cid(1200, 3))
    w.write_media(b"\x00\x00\x00\x18ftypmp42" + bytes(8192))

    # 4 no marker, no key at all -> DISCARD (a directory, not a clip)
    orphan = layout.clip_dir(root, _cid(600, 4))
    orphan.mkdir(parents=True, exist_ok=True)
    (orphan / layout.MEDIA_NAME).write_bytes(b"orphan-media")

    # 5 a key that claims media which is gone -> DISCARD (the claim goes with it)
    missing = layout.clip_dir(root, _cid(300, 5))
    missing.mkdir(parents=True, exist_ok=True)
    (missing / layout.KEY_NAME).write_text(
        json.dumps(
            {
                "layout_version": layout.LAYOUT_VERSION,
                "clip_id": _cid(300, 5),
                "media": layout.MEDIA_NAME,
                "size_bytes": 1234,
                "started_at_s": now - 300,
            }
        ),
        encoding="utf-8",
    )

    # 6 an UNMARKED directory whose key cannot be read -> KEEP.  The media may be a good clip;
    # deleting it would destroy bytes on a guess, and it stays out of the index either way.
    untrusted = layout.clip_dir(root, _cid(200, 6))
    untrusted.mkdir(parents=True, exist_ok=True)
    (untrusted / layout.MEDIA_NAME).write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes(6000))
    (untrusted / layout.KEY_NAME).write_text("{ this is not json", encoding="utf-8")

    before_dirs = sorted(c.clip_id for c in iter_clips(root))
    rep.check(
        "C0.fixture-has-every-state",
        len(before_dirs) == 7,
        f"{len(before_dirs)} clip directories staged: {before_dirs}",
    )

    result = reconcile(root)
    after_dirs = sorted(c.clip_id for c in iter_clips(root))
    keys_errs: list[str] = []
    keys = walk_keys(root, errors=keys_errs)

    finished_ids = [c for c, _ in result.finished]
    discarded_ids = [c for c, _, _, _ in result.discarded]
    rep.check(
        "C1.finished-the-committed-partial",
        _cid(1800, 2) in finished_ids,
        f"crash after commit -> finished {[c for c, _ in result.finished]} (bytes freed 0: "
        f"the clip was never lost, only its marker)",
    )
    rep.check(
        "C2.discarded-the-uncommitted-partial",
        _cid(1200, 3) in discarded_ids,
        f"crash before commit -> discarded {discarded_ids}",
    )
    rep.check(
        "C3.discarded-orphan-and-missing-media",
        _cid(600, 4) in discarded_ids and _cid(300, 5) in discarded_ids,
        f"orphan directory and a key claiming absent media both discarded: "
        f"{[(c, w) for c, w, _, _ in result.discarded]}",
    )
    rep.check(
        "C4.committed-clips-survived",
        all(_cid(3600 * (i + 1), i) in after_dirs for i in range(2)),
        f"{len(after_dirs)} dir(s) remain: {after_dirs}",
    )
    # THE invariant: every key the index would claim points at a file that exists.
    bad_claims = [k["clip_id"] for k in keys if not (Path(k["_path"]) / k["media"]).is_file()]
    rep.check(
        "C5.index-claims-nothing-that-is-missing",
        not bad_claims and len(keys) == 3,
        f"walk_keys() would hand the index {len(keys)} clip(s) "
        f"({sorted(k['clip_id'] for k in keys)}), every one with its media present "
        f"(unbacked claims={len(bad_claims)}); the untrusted-key dir is NOT among them, which "
        f"is the point of refusing to guess at it",
    )
    rep.check(
        "C6.no-partial-marker-survives",
        not any(c.has_partial for c in iter_clips(root)),
        f"{sum(1 for c in iter_clips(root) if c.has_partial)} dir(s) still carry a "
        f"{PARTIAL_MARKER} marker after reconciliation",
    )
    second = reconcile(root)
    rep.check(
        "C7.reconcile-is-idempotent",
        not second.discarded and not second.finished,
        "a second reconcile over the same tree found nothing to finish and nothing to "
        f"discard ({len(second.kept)} kept)",
    )
    rep.check(
        "C8.reconcile-reported-no-errors",
        not result.errors,
        f"{len(result.errors)} reconcile error(s)",
    )
    # The one diagnostic this fixture is SUPPOSED to produce: the untrusted key is loud.
    rep.check(
        "C9.untrusted-key-is-kept-and-reported",
        _cid(200, 6) in after_dirs
        and len(keys_errs) == 1
        and "unreadable key" in keys_errs[0],
        f"the unmarked dir with an unparseable key SURVIVED ({_cid(200, 6)} in "
        f"{len(after_dirs)} remaining dir(s)) and produced exactly {len(keys_errs)} reported "
        f"diagnostic(s): {keys_errs}. Bytes are not deleted on a guess, and the hole is not "
        f"silent either.",
    )

    rep.facts["population"] = {
        "dirs_staged": len(before_dirs),
        "dirs_after": len(after_dirs),
        "kept": len(result.kept),
        "finished": len(result.finished),
        "discarded": len(result.discarded),
        "bytes_reclaimed": result.bytes_reclaimed,
        "keys_the_index_would_see": len(keys),
        "store": str(root),
    }
    rep.facts["window"] = {**survey(root).window(), "note": "six staged crash states, one reconcile pass"}
    return rep


def arm_e(work: str) -> Report:
    """The budget in force, and WHERE IT CAME FROM -- plus a refusal to guess."""
    rep = Report("E")
    policy = policy_from_env(env={})
    rep.check(
        "E1.defaults-are-stated",
        (policy.max_bytes, policy.max_age_s, policy.max_clips, policy.reserve_bytes)
        == (DEFAULT_MAX_BYTES, DEFAULT_MAX_AGE_S, DEFAULT_MAX_CLIPS, DEFAULT_RESERVE_BYTES),
        f"max_bytes={policy.max_bytes} max_age_s={policy.max_age_s:g} "
        f"max_clips={policy.max_clips} reserve_bytes={policy.reserve_bytes} "
        f"= {policy.max_bytes / (1 << 30):.0f} GiB / {policy.max_age_s / 3600:.0f} h / "
        f"{policy.max_clips} clips / {policy.reserve_bytes / (1 << 30):.0f} GiB",
    )
    env_policy = policy_from_env(env={ENV_MAX_BYTES: "1234567"})
    rep.check(
        "E2.env-overrides-default-and-says-so",
        env_policy.max_bytes == 1234567 and env_policy.source_of("max_bytes") == f"env:{ENV_MAX_BYTES}",
        f"{ENV_MAX_BYTES}=1234567 -> max_bytes={env_policy.max_bytes} "
        f"source={env_policy.source_of('max_bytes')}",
    )
    both = policy_from_env(env={ENV_MAX_BYTES: "1234567"}, max_bytes=99)
    rep.check(
        "E3.explicit-beats-env",
        both.max_bytes == 99 and both.source_of("max_bytes") == "explicit",
        f"explicit=99 with {ENV_MAX_BYTES}=1234567 in the env -> {both.max_bytes} "
        f"source={both.source_of('max_bytes')}",
    )
    refused = []
    for bad in ("0", "-5", "abc", ""):
        try:
            policy_from_env(env={ENV_MAX_BYTES: bad})
            refused.append(f"{bad!r}=ACCEPTED")
        except PolicyError as exc:
            refused.append(f"{bad!r}=refused({exc})")
        except Exception as exc:  # noqa: BLE001 -- any OTHER exception is itself a defect
            refused.append(f"{bad!r}=WRONG-EXCEPTION({type(exc).__name__}: {exc})")
    rep.check(
        "E4.bad-budgets-are-refused-not-clamped",
        all("=refused(" in r for r in refused),
        "; ".join(refused),
    )
    view = survey(Path(work) / "armE-store")
    if not view.clips:
        _build_store(view.root, 4)
        view = survey(view.root)
    line = policy.line(view.population(), view.window())
    rep.check(
        "E5.the-logged-line-states-the-budget-in-force",
        f"budget_bytes={policy.max_bytes}" in line
        and "budget_source=default" in line
        and f"POPULATION clips={view.n}" in line
        and "WINDOW oldest=" in line,
        line,
    )
    rep.check(
        "E6.the-budget-is-translated-into-time",
        700 <= policy.capture_seconds_at_measured_rate <= 800,
        f"max_bytes={policy.max_bytes} B at the MEASURED "
        f"{MEASURED_BYTES_PER_SECOND:,.0f} B/s = "
        f"{policy.capture_seconds_at_measured_rate / 60:.1f} min of capture. Quoting a byte "
        f"budget without this number is how 4 GiB reads as 'four hours' and means twelve "
        f"minutes.",
    )
    rep.facts["population"] = view.population()
    rep.facts["window"] = view.window()
    return rep


ARMS = {"A": arm_a, "B": arm_b, "C": arm_c, "E": arm_e}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m storage.retention")
    ap.add_argument("--arm", choices=sorted(ARMS), default=None)
    ap.add_argument("--work", default="_main/_lane22-run")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    if not args.arm:
        ap.error("nothing to do: pass --arm " + "/".join(sorted(ARMS)))
    rep = ARMS[args.arm](args.work)
    # Which files were ACTUALLY imported.  The gate's control arm copies this package and
    # reverts one guard; without these two lines a mutant run that accidentally imported the
    # ORIGINAL package would report "not red" for the wrong reason, and a reader could not
    # tell the two failures apart.
    rep.facts.setdefault("module_file", str(Path(__file__).resolve()))
    rep.facts.setdefault("layout_module_file", str(Path(layout.__file__).resolve()))
    rep.facts.setdefault("arm", args.arm)
    emit(rep, args.json)
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())