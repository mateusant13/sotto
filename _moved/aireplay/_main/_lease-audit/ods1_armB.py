#!/usr/bin/env python3
"""ODS-1 -- the first On-Disk Search instrument.   ARM A: a synthetic store with KNOWN instants.

WHAT IT DOES
    Walks one library root and emits a timeline of (start, end, source) rows WITHOUT reading
    pixels: no SPS/PPS is parsed, no audio or video stream is decoded, no image is read.
    Every row carries the EVIDENCE path it came from and the PRIORITY RANK of that source.

PRIORITY (this step's contract; the highest rank that carries a value wins)
    clip-id(1) > key.json(2) > db(3) > container/moov(4) > mtime-derived(5)

    start  = the clip-id start (rank 1) when present, else UNKNOWN.
    end    = the highest-rank source that carries one: key ended_at_s (2) > db duration (3)
             > container duration (4) > mtime (5).
    A container whose parse is REFUSED has NO duration: it prints UNKNOWN, never 0.
    An absent value prints UNKNOWN, never 0 and never a guess.

TWO SANITY TRAPS THIS INSTRUMENT MUST NOT FALL INTO
    1. mp4_writer.cpp:257, :272, :293 write creation_time / modification_time as the literal
       0 (both fields, all three of mvhd/tkhd/mdhd).  A zero here is NOT 1970-01-01 and it is
       NOT a date at all: it is the writer's "no time" and it is COUNTED, never printed as a
       date.  THE INSTRUMENT NEVER PRINTS A DATE FOR IT.
    2. A missing value is UNKNOWN.  It is never 0 and never a guess.

EXIT CODES (a contract; the caller may branch on them)
    0   clean store: zero findings, zero refusals, self-audit green
    1   findings and/or refusals present (the store is RED)
    2   run refused: bad arguments, unreadable --layout, root inside a PROTECTED path
    3   self-audit RED: one of this instrument's own invariants failed

READ-ONLY.  This run opens no audio or video device, builds nothing, writes nothing into the
store, and runs no git command.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ============================ the contract's constants =====================================
# Every value below is either READ from a file (cited) or COMPUTED here and labelled.

PAD_S = 0.10
# READ specs/02-asr.md:165 -- "| PAD_S | 0.10 either side (this is why recorded segments
# overlap) | probe-onnx-asr-split.py:77 |".  It is defined for ASR SEGMENT padding; here it is
# used as the overlap tolerance for two CLIP intervals -- see TO-BE-ANSWERED-BY-OWNER.md.

DUR_TOLERANCE_MS = 1
# An agreed rounding allowance between two duration sources describing the same media.
# Chosen by this lane; a tolerance, not a measurement.

CLIPID_KEY_TOLERANCE_S = 0.0
# READ src/storage/layout.py:433 -- the commit key builder writes
#   "started_at_s": parse_clip_id(self.clip_id).started_at_s
# i.e. THE KEY COPIES THE CLIP ID VERBATIM, so any disagreement at all is a contradiction.

MP4_EPOCH_UNIX_S = datetime(1904, 1, 1, tzinfo=timezone.utc).timestamp()
# COMPUTED in this instrument at startup (not copied from a doc): the mp4 epoch is
# 1904-01-01T00:00:00Z = -2082844800.0 UNIX seconds.  Used ONLY to show what a NON-ZERO mp4
# stamp would mean; this writer never writes one (traps above).

RANK_CLIP_ID, RANK_KEY, RANK_DB, RANK_CONTAINER, RANK_MTIME = 1, 2, 3, 4, 5
RANK_LEGEND = "clip-id(1) > key.json(2) > db(3) > container/moov(4) > mtime-derived(5)"
RANK_NAME = {1: "clip-id", 2: "key.json", 3: "db", 4: "moov", 5: "mtime"}
UNKNOWN = "UNKNOWN"


# vocabulary of boxes this instrument IMPLEMENTS.  Anything outside it is REFUSED, not guessed.
TOP_VOCAB = {b"ftyp", b"moov", b"mdat", b"free", b"skip", b"wide", b"pnot", b"uuid"}
MOOV_CHILDREN = {b"mvhd", b"trak", b"udta", b"mvex"}
TRAK_CHILDREN = {b"tkhd", b"mdia", b"edts", b"tref"}
MDIA_CHILDREN = {b"mdhd", b"hdlr", b"minf"}
MINF_CHILDREN = {b"vmhd", b"smhd", b"dinf", b"nmhd", b"stbl"}
STBL_CHILDREN = {b"stsd", b"stts", b"stsc", b"stsz", b"stco", b"co64", b"ctts"}
CONTAINER_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}
PRUNE_DIRS = {".git", "node_modules", "__pycache__", "models", "build", "runs", ".venv"}


def iso(ts):
    """A UTC string, or the literal UNKNOWN.  Never a number, never None."""
    if ts is None:
        return UNKNOWN
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def _box_at(buf, off, end, vocab, where, refusal):
    """One box header.  On the FIRST bad cause it fills refusal and returns None."""
    if off + 8 > end:
        refusal["code"] = "R-BOX-TRUNCATED"
        refusal["detail"] = ("box header at offset %d in %s extends past EOF (%d bytes left, "
                             "8 needed)" % (off, where, end - off))
        return None
    size, typ = struct.unpack(">I4s", buf[off:off + 8])
    hdr = 8
    if size == 1:
        if off + 16 > end:
            refusal["code"] = "R-BOX-TRUNCATED"
            refusal["detail"] = "64-bit box header at %d in %s extends past EOF" % (off, where)
            return None
        size = struct.unpack(">Q", buf[off + 8:off + 16])[0]
        hdr = 16
    if size == 0:
        size = end - off
    if size < hdr:
        refusal["code"] = "R-BOX-TRUNCATED"
        refusal["detail"] = ("box %r at %d in %s declares size %d, smaller than its own "
                             "%d-byte header" % (typ.decode("latin-1"), off, where, size, hdr))
        return None
    if off + size > end:
        refusal["code"] = "R-BOX-TRUNCATED"
        refusal["detail"] = ("box %r at %d in %s declares size %d but only %d bytes remain: "
                             "it claims past EOF"
                             % (typ.decode("latin-1"), off, where, size, end - off))
        return None
    if vocab is not None and typ not in vocab:
        refusal["code"] = "R-BOX-UNKNOWN"
        refusal["detail"] = ("box %r at %d in %s is outside the implemented vocabulary"
                             % (typ.decode("latin-1"), off, where))
        return None
    return (typ, off + hdr, off + size)


def _children(buf, start, end, vocab, where, refusal):
    out = []
    off = start
    while off < end:
        box = _box_at(buf, off, end, vocab, where, refusal)
        if box is None:
            return out, False
        out.append(box)
        off = box[2]
    return out, True


# --------------------------------------------------------------------------------------------
# The moov walk.  ONE pass: mvhd + every trak's tkhd/hdlr/mdhd/stts.  Each box is only read
# if its version is the one implemented; otherwise a REFUSAL is recorded and NO value is
# produced (a refused box yields UNKNOWN, never a guess and never a 0).
# --------------------------------------------------------------------------------------------

def walk_mvhd(facts, buf, b, e):
    h = buf[b:e]
    if not h:
        return
    if h[0] != 0:
        facts["refusal"].setdefault("code", "R-BOX-VERSION")
        facts["refusal"].setdefault("detail", "mvhd version %r: only v0 (32-bit fields) is "
                                    "implemented, so NO mvhd value is read" % h[0])
        return
    if len(h) < 20:
        return
    creation, modification, timescale, duration = struct.unpack(">IIII", h[4:20])
    for name, val in (("creation_time", creation), ("modification_time", modification)):
        if val == 0:
            facts["zero_epoch_fields"]["mvhd:" + name] = facts["zero_epoch_fields"].get(
                "mvhd:" + name, 0) + 1
        else:
            # COMPUTED offset printed as a date: what a NON-ZERO mp4 stamp WOULD mean.
            facts["mvhd_" + name + "_iso"] = iso(MP4_EPOCH_UNIX_S + val)
    facts["mvhd_timescale"] = timescale
    if timescale:
        facts["mvhd_duration_s"] = duration / float(timescale)
    else:
        facts["refusal"].setdefault("code", "R-NO-TIMESCALE")
        facts["refusal"].setdefault("detail", "mvhd timescale == 0: the duration ticks have no "
                                    "time base")


def walk_tkhd(facts, buf, b, e):
    h = buf[b:e]
    if not h:
        return
    if h[0] != 0:
        facts["refusal"].setdefault("code", "R-BOX-VERSION")
        facts["refusal"].setdefault("detail", "tkhd version %r: only v0 is implemented"
                                    % h[0])
        return
    if len(h) < 12:
        return
    creation, modification = struct.unpack(">II", h[4:12])
    for name, val in (("creation_time", creation), ("modification_time", modification)):
        if val == 0:
            facts["zero_epoch_fields"]["tkhd:" + name] = facts["zero_epoch_fields"].get(
                "tkhd:" + name, 0) + 1


def read_mdhd(facts, buf, b, e, trak):
    h = buf[b:e]
    if not h:
        return
    if h[0] != 0:
        facts["refusal"].setdefault("code", "R-BOX-VERSION")
        facts["refusal"].setdefault("detail", "mdhd version %r: only v0 (32-bit fields) is "
                                    "implemented" % h[0])
        return
    if len(h) < 20:
        facts["refusal"].setdefault("code", "R-BOX-TRUNCATED")
        facts["refusal"].setdefault("detail", "mdhd body is %d bytes, shorter than the v0 "
                                    "layout (20)" % len(h))
        return
    creation, modification, timescale, duration = struct.unpack(">IIII", h[4:20])
    for name, val in (("creation_time", creation), ("modification_time", modification)):
        if val == 0:
            facts["zero_epoch_fields"]["mdhd:" + name] = facts["zero_epoch_fields"].get(
                "mdhd:" + name, 0) + 1
    trak["mdhd"] = {"timescale": timescale, "duration_ticks": duration,
                    "creation_time": creation, "modification_time": modification}


def read_stts(facts, buf, b, e, trak):
    """Sample-to-duration table.  Duration = sum(sample_count * sample_delta)."""
    h = buf[b:e]
    if len(h) < 8:
        facts["refusal"].setdefault("code", "R-BOX-TRUNCATED")
        facts["refusal"].setdefault("detail", "stts body is %d bytes, shorter than entry_count" % len(h))
        return
    n = struct.unpack(">I", h[4:8])[0]
    total = 0
    ticks = 0
    pos = 8
    for _ in range(n):
        if pos + 8 > len(h):
            facts["refusal"].setdefault("code", "R-BOX-TRUNCATED")
            facts["refusal"].setdefault("detail", "stts entry past box end")
            return
        cnt, delta = struct.unpack(">II", h[pos:pos + 8])
        total += cnt
        ticks += cnt * delta
        pos += 8
    trak["stts"] = True
    trak["sample_count"] = total
    trak["sample_ticks"] = ticks


def walk_trak(facts, buf, b, e):
    trak = {"handler": None, "mdhd": None, "stts": False, "sample_count": None,
            "sample_ticks": 0, "duration_ms": None, "duration_s": None}
    kids, ok = _children(buf, b, e, TRAK_CHILDREN, "trak", facts["refusal"])
    if not ok:
        return
    for typ, b2, e2 in kids:
        if typ == b"tkhd":
            walk_tkhd(facts, buf, b2, e2)
        if typ != b"mdia":
            continue
        mkids, mok = _children(buf, b2, e2, MDIA_CHILDREN, "mdia", facts["refusal"])
        if not mok:
            continue
        for t2, b3, e3 in mkids:
            if t2 == b"hdlr":
                h = buf[b3:e3]
                if len(h) >= 12:
                    trak["handler"] = h[8:12].decode("latin-1")
            if t2 == b"mdhd":
                read_mdhd(facts, buf, b3, e3, trak)
            if t2 != b"minf":
                continue
            ikids, iok = _children(buf, b3, e3, MINF_CHILDREN, "minf", facts["refusal"])
            if not iok:
                continue
            for t3, b4, e4 in ikids:
                if t3 != b"stbl":
                    continue
                skids, sok = _children(buf, b4, e4, STBL_CHILDREN, "stbl", facts["refusal"])
                if not sok:
                    continue
                for t4, b5, e5 in skids:
                    if t4 == b"stts":
                        read_stts(facts, buf, b5, e5, trak)
    facts["traks"].append(trak)


def walk_moov(facts, buf, b, e):
    kids, ok = _children(buf, b, e, MOOV_CHILDREN, "moov", facts["refusal"])
    if not ok:
        return
    for typ, b2, e2 in kids:
        if typ == b"mvhd":
            walk_mvhd(facts, buf, b2, e2)
        if typ == b"trak":
            walk_trak(facts, buf, b2, e2)


def finish_durations(facts):
    """Turn the trak tables into seconds.  A refusal here means UNKNOWN, never 0."""
    for trak in facts["traks"]:
        mdhd = trak.get("mdhd")
        if mdhd is None:
            continue
        if mdhd["timescale"] == 0:
            facts["refusal"].setdefault("code", "R-NO-TIMESCALE")
            facts["refusal"].setdefault("detail", "mdhd timescale == 0 in %s: the duration ticks "
                                        "(%d) exist but there is no time base to divide by, so "
                                        "NO duration is produced (not 0)"
                                        % (facts["path"], mdhd["duration_ticks"]))
            return
        if not trak["stts"]:
            facts["refusal"].setdefault("code", "R-NO-DURATION")
            facts["refusal"].setdefault("detail", "trak %r has mdhd (timescale %d) but no stts: "
                                        "the sample-to-duration table is absent, so its "
                                        "duration is UNKNOWN"
                                        % (trak["handler"], mdhd["timescale"]))
            return
        secs = trak["sample_ticks"] / float(mdhd["timescale"])
        trak["duration_s"] = secs
        trak["duration_ms"] = int(round(secs * 1000.0))
        facts["trak_durations_s"].append(secs)


def _container_facts(path):
    """THE ONE container entry point.  Read-only; no stream is touched, no pixel is read."""
    facts = {"path": str(path), "bytes": None, "refusal": {}, "moov_present": False,
             "ftyp_seen": False, "traks": [], "zero_epoch_fields": {},
             "mvhd_duration_s": None, "mvhd_timescale": None,
             "mvhd_creation_time_iso": None, "mvhd_modification_time_iso": None,
             "trak_durations_s": []}
    try:
        buf = Path(path).read_bytes()
    except OSError as exc:
        facts["refusal"] = {"code": "R-UNREADABLE", "detail": "%s: %s" % (path, exc)}
        return facts
    facts["bytes"] = len(buf)
    off = 0
    ftyp = False
    while off < len(buf):
        # record what the walk reached BEFORE this box is read: if this box kills the walk,
        # the terminal chain can say what had already been found
        facts["ftyp_seen"] = ftyp
        box = _box_at(buf, off, len(buf), TOP_VOCAB, "top-level", facts["refusal"])
        if box is None:
            return facts
        typ, body, bend = box
        if typ == b"ftyp":
            ftyp = True
        if typ == b"moov":
            facts["moov_present"] = True
            walk_moov(facts, buf, body, bend)
            if facts["refusal"]:
                return facts
        off = bend
    if not ftyp:
        facts["refusal"] = {"code": "R-NO-FTYP",
                            "detail": "no ftyp box in %d bytes: this is not a recognised "
                                      "container brand" % len(buf)}
        return facts
    if not facts["moov_present"]:
        facts["refusal"] = {"code": "R-NO-MOOV",
                           "detail": "no moov box: the container carries no sample tables "
                                     "(the writer flushed nothing)"}
        return facts
    finish_durations(facts)
    return facts


def _terminal(facts):
    """Name what the first cause made IMPOSSIBLE, so a reader can match either word.

    "box 40 claims size 1935764596 but only 16 bytes remain" is true and is almost useless on
    its own: it names the mechanism, not what the instrument could therefore not produce.  The
    terminal names that, from what the walk actually reached -- no ftyp reached, no moov reached,
    a box in an unimplemented version.  The FIRST cause stays the code (that is the thing to
    fix); the terminal is what stayed UNKNOWN.  Both are printed, in this order.
    """
    rf = facts.get("refusal") or {}
    if not rf:
        return facts
    code = rf.get("code")
    if code == "R-UNREADABLE":
        term = ("R-DURATION-UNKNOWN",
                "the file could not be opened at all, so its duration is UNKNOWN, never 0")
    elif not facts.get("ftyp_seen"):
        term = ("R-NO-FTYP", "the walk never reached an ftyp box, so the container brand was "
                "never recognised")
    elif not facts.get("moov_present"):
        term = ("R-NO-MOOV", "no moov box was reached, so there is no sample table to read a "
                "duration from")
    elif code in ("R-BOX-VERSION", "R-NO-TIMESCALE"):
        term = ("R-NO-DURATION", "the box that would carry the duration is in a version this "
                "instrument does not parse, so its duration stays UNKNOWN, never 0")
    else:
        term = ("R-DURATION-UNKNOWN", "the duration could not be produced from the bytes that "
                "were readable")
    rf["terminal_code"] = term[0]
    rf["terminal_detail"] = term[1]
    return facts


def container_facts(path):
    """THE ONE container entry point, with the refusal chain closed."""
    return _terminal(_container_facts(path))


# =========================== the product's own layout module =================================
# ONE code path: every disk fact goes through the repo's own layout.py.  Nothing below
# re-implements a naming rule, a sidecar rule, a clip-id rule or a key rule.

def load_layout(layout_path):
    p = Path(layout_path).resolve()
    if not p.is_file():
        raise SystemExit("E-LAYOUT-MISSING: --layout %s is not a file" % layout_path)
    spec = importlib.util.spec_from_file_location("ods_layout", p)
    if spec is None or spec.loader is None:
        raise SystemExit("E-LAYOUT-UNREADABLE: cannot load %s" % layout_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ods_layout"] = mod
    spec.loader.exec_module(mod)
    return mod


def read_db_dups(db_path):
    """The db's OWN refusal to hold a second row with the same content_key.

    schema.sql:44 makes video.content_key UNIQUE, so a duplicate insert is refused by the
    index itself.  This is a fact the instrument can MEASURE on the live db: count the
    content_keys that appear more than once (must be 0, or the UNIQUE constraint is gone).
    """
    counts = {}
    con = sqlite3.connect("file:%s?mode=ro" % path_to_file_uri(db_path), uri=True)
    con.row_factory = sqlite3.Row
    try:
        tbls = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "video" not in tbls:
            return {"tables": tbls, "present": False, "duplicate_content_keys": {},
                    "rows": 0, "rows_raw": []}
        rows = con.execute("SELECT content_key, path, duration_ms, missing, state, "
                           "size_bytes, mtime_ns FROM video").fetchall()
    finally:
        con.close()
    counts = {}
    for r in rows:
        k = r["content_key"]
        counts.setdefault(k, []).append(dict(r))
    dups = {k: v for k, v in counts.items() if len(v) > 1}
    return {"tables": tbls, "present": True, "rows": len(rows), "rows_raw": [dict(r) for r in rows],
            "duplicate_content_keys": dups}


def path_to_file_uri(p):
    s = str(Path(p).resolve()).replace("\\", "/")
    return s if s.startswith("/") else "/" + s


def find_index_db(root):
    """The index file, found by name under the root (bounded walk, no whole-drive scan)."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        for f in filenames:
            if f.endswith(".db") or f.endswith(".sqlite") or f.endswith(".sqlite3"):
                hits.append(Path(dirpath) / f)
        if len(hits) > 8:
            break
    return hits


# =============================== the clip walk ==============================================

def analyse_clip(L, c, db_index):
    """One clip directory -> everything the instrument knows about it, through layout.py."""
    out = {"clip_id": c.clip_id, "path": str(c.path), "errors": list(c.errors),
           "size_bytes": c.size_bytes, "started_at_s": c.started_at_s,
           "has_key": c.has_key, "has_media": c.has_media, "has_partial": c.has_partial}
    sc = L.sidecars(c.path)
    out["sidecars"] = {k: (str(v) if v is not None else None) for k, v in sc.items()}
    out["mtime_ns"] = None
    media = sc.get("media")
    if media and Path(media).is_file():
        st = Path(media).stat()
        out["mtime_ns"] = st.st_mtime_ns
    cl = L.classify(c)
    out["verdict"] = cl.verdict
    out["verdict_reason"] = cl.reason
    out["key_error"] = cl.key_error
    key = None
    if c.has_key and sc.get("key") and Path(sc["key"]).is_file():
        try:
            key = L.read_key(sc["key"])
        except Exception as exc:
            out["key_error"] = "%s: %s" % (type(exc).__name__, exc)
    out["key"] = key
    # the key's duration claim and its own end
    out["key_duration_ms"] = None if not key else key.get("duration_ms")
    out["key_started_at_s"] = None if not key else key.get("started_at_s")
    out["key_ended_at_s"] = None if not key else key.get("ended_at_s")
    out["key_content_key"] = None if not key else key.get("content_key")
    # the identity claim, re-checked against the bytes
    out["sha256"] = None
    if c.has_media and media and Path(media).is_file():
        try:
            out["sha256"] = L.sha256_file(str(media))
        except Exception as exc:
            out["sha256_error"] = "%s: %s" % (type(exc).__name__, exc)
    out["media_path"] = str(media) if media else None
    # the container
    cf = None
    if c.has_media and media and Path(media).is_file():
        cf = container_facts(media)
    out["container"] = cf
    # the db row for this exact path
    out["db_row"] = db_index.get(str(media)) if media else None
    return out


def sha256_file_any(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# =============================== the timeline ==============================================

def video_trak_ms(traks):
    """The container duration a comparison must use: the VIDEO trak, never the max.

    max() is the exact trap this instrument names in its own C2TRAK message ("a reader
    that takes max, min or the first trak gets three different clip lengths"), so C07 and
    C08 have to use the SAME rule the row itself uses for its rank-4 candidate.  A
    container with no readable trak gives None -- UNKNOWN, never 0.
    """
    if not traks:
        return None
    for t in traks:
        if t.get("handler") == "vide" and t.get("duration_ms") is not None:
            return t["duration_ms"]
    for t in traks:
        if t.get("duration_ms") is not None:
            return t["duration_ms"]
    return None


def clip_timeline(r):
    """One clip -> one (start, end, source) row with every candidate and its rank.

    start = rank 1 (the clip id) when present.
    end   = the highest rank that carries a value: key ended_at_s (2), db duration (3),
            container duration (4), mtime (5).  An absent value is UNKNOWN, never 0.
    """
    start = r["started_at_s"]
    start_src = {"rank": RANK_CLIP_ID, "source": "clip-id", "path": r["path"],
                 "value": start, "detail": "parse_clip_id(%s).started_at_s" % r["clip_id"]}
    cands = []
    # rank 2 -- key.json
    if r["key_ended_at_s"] is not None:
        cands.append({"rank": RANK_KEY, "source": "key.json", "path": r["sidecars"]["key"],
                     "value": r["key_ended_at_s"], "detail": "key ended_at_s"})
    # rank 3 -- db duration
    dbr = r.get("db_row")
    if dbr and dbr.get("duration_ms") is not None:
        cands.append({"rank": RANK_DB, "source": "db", "path": dbr.get("path"),
                     "value": (start + dbr["duration_ms"] / 1000.0) if start is not None else None,
                     "detail": "db duration_ms=%d added to the rank-1 start"
                               % dbr["duration_ms"]})
    # rank 4 -- container / moov
    cf = r.get("container")
    if cf and not cf.get("refusal") and cf.get("traks"):
        durs = [t["duration_ms"] for t in cf["traks"] if t.get("duration_ms") is not None]
        if durs:
            # the VIDEO track is the clip's own length; the audio track is not a contradiction
            vids = [t for t in cf["traks"] if t.get("handler") == "vide" and t.get("duration_ms") is not None]
            chosen = vids[0] if vids else cf["traks"][0]
            cands.append({"rank": RANK_CONTAINER, "source": "moov",
                         "path": r["media_path"],
                         "value": (start + chosen["duration_ms"] / 1000.0) if start is not None else None,
                         "detail": "moov trak handler=%r duration_ms=%d (video trak %d traks)"
                                   % (chosen.get("handler"), chosen["duration_ms"], len(cf["traks"]))})
    # rank 5 -- mtime
    if r.get("mtime_ns") is not None:
        cands.append({"rank": RANK_MTIME, "source": "mtime", "path": r["media_path"],
                     "value": r["mtime_ns"] / 1e9, "detail": "media mtime as the end anchor"})
    chosen = None
    for c in cands:
        if c["value"] is not None:
            chosen = c
            break
    row = {"subject": r["clip_id"], "kind": "clip", "dir": r["path"],
           "verdict": r["verdict"], "clip_id": r["clip_id"],
           "start": start, "start_source": start_src,
           "end": (None if chosen is None else chosen["value"]),
           "end_source": chosen, "end_candidates": cands,
           "evidence_paths": [c["path"] for c in cands if c.get("path")],
           "container_refusal": (cf or {}).get("refusal") or {},
           "zero_epoch_fields": (cf or {}).get("zero_epoch_fields") or {},
           "key_error": r["key_error"], "sha256": r["sha256"],
           "key_content_key": r["key_content_key"],
           "sidecars": r.get("sidecars") or {},
           "media_path": r.get("media_path"),
           # the row carries what its own checks compare: the container facts, the key, the db
           # row and the mtime.  Nothing below is allowed to fetch them a second time.
           "container": cf, "mtime_ns": r.get("mtime_ns"),
           "key": r.get("key"), "key_duration_ms": r.get("key_duration_ms"),
           "key_started_at_s": r.get("key_started_at_s"),
           "key_ended_at_s": r.get("key_ended_at_s"), "has_key": r.get("has_key"),
           "db_row": r.get("db_row")}
    if r.get("sha256_error"):
        row["sha256_error"] = r["sha256_error"]
    return row

def foreign_timeline(f, db_row, sha256=None, sha256_error=None):
    """A file directly under the library root that is NOT a clip-id directory."""
    cf = container_facts(f)
    refusal = cf.get("refusal") or {}
    mtime_ns = Path(f).stat().st_mtime_ns if Path(f).exists() else None
    start_src = {"rank": RANK_MTIME, "source": "mtime", "path": str(f),
                 "value": (mtime_ns / 1e9) if mtime_ns else None,
                 "detail": "mtime as the rank-5 anchor (no clip id, no key)"}
    cands = []
    cont_ms = None if refusal else video_trak_ms(cf.get("traks"))
    if db_row and db_row.get("duration_ms") is not None:
        cands.append({"rank": RANK_DB, "source": "db", "path": db_row.get("path"),
                      "value": db_row["duration_ms"] / 1000.0,
                      "detail": "db duration_ms=%d (seconds)" % db_row["duration_ms"]})
    if cont_ms is not None:
        cands.append({"rank": RANK_CONTAINER, "source": "moov", "path": str(f),
                      "value": cont_ms / 1000.0,
                      "detail": "moov VIDEO trak duration_ms=%d (max() is the trap this"
                                " instrument names in its own C2TRAK message, so it is not"
                                " used as a duration here)" % cont_ms})
    dur = None
    for c in cands:
        if c["value"] is not None:
            dur = c
            break
    anchor = (mtime_ns / 1e9) if mtime_ns else None
    row = {"subject": Path(f).name, "kind": "foreign", "path": str(f),
           "verdict": None, "clip_id": None, "start": None, "end": None,
           "start_source": start_src, "end_source": None, "end_candidates": cands,
           "duration": dur, "evidence_paths": [str(f)],
           "container_refusal": refusal, "zero_epoch_fields": cf.get("zero_epoch_fields") or {},
           # a foreign row is compared by C08/C07 too, so it carries the same facts.
           "container": cf, "db_row": db_row, "key": None,
           "key_duration_ms": None, "key_started_at_s": None, "key_ended_at_s": None,
           "sha256": sha256}
    if sha256_error:
        row["sha256_error"] = sha256_error
    if refusal:
        return row
    if dur is not None and anchor is not None:
        row["start"] = anchor - dur["value"]
        row["end"] = anchor
        row["duration_source"] = dur
        # the end of a foreign row comes from the very candidate that chose its duration, so
        # the row carries that rank: a reader must see WHICH source put 2.0 s in the end.
        row["end_source"] = dur
    return row


# =============================== the contradiction engine ===================================

def row_path(r):
    """Where this row lives: a clip row carries dir, a foreign row carries path."""
    return str(r.get("path") or r.get("dir") or UNKNOWN)


def row_key_path(r):
    """The key.json that sank this row, when there is one."""
    sc = r.get("sidecars") or {}
    if sc.get("key"):
        return str(sc["key"])
    return row_path(r)

def find_contradictions(rows, db_info, L, root):
    """Every check in one place.  Each finding names its evidence PATH(S) and the ranks used."""
    f = []
    known = [r for r in rows if r.get("start") is not None and r.get("end") is not None]
    real = [r for r in known if r["end"] > r["start"]]
    # An overlap is a contradiction between two CLAIMS about when a body was recorded.
    # A rank-5 mtime is not such a claim: an imported library file carries the time it
    # ARRIVED, so "it overlaps a clip" says nothing.  The overlap test therefore runs over
    # the rows whose start is rank 1 (clip-id) or rank 2 (key.json); the mtime-anchored rows
    # are still listed, still take part in C05/C07/C08, and are still reported when the db
    # or the container disagrees with them.
    claimed = [r for r in real if (r.get("start_source") or {}).get("rank")
               in (RANK_CLIP_ID, RANK_KEY)]

    # ---- C1 INTERVAL OVERLAP -------------------------------------------------------------
    for i in range(len(claimed)):
        for j in range(i + 1, len(claimed)):
            a, b = claimed[i], claimed[j]
            ov = min(a["end"], b["end"]) - max(a["start"], b["start"])
            if ov > PAD_S:
                f.append({"cls": "C01", "name": "INTERVAL OVERLAP", "severity": "red",
                          "subject": "%s vs %s" % (a["subject"], b["subject"]),
                          "detail": ("intervals overlap by %.3f s, which is more than the "
                                     "PAD_S %.2f s tolerance" % (ov, PAD_S)),
                          "evidence_paths": [a["path"] if "path" in a else a["dir"],
                                             b["path"] if "path" in b else b["dir"]],
                          "ranks": [a["end_source"]["rank"] if a.get("end_source") else None,
                                    b["end_source"]["rank"] if b.get("end_source") else None],
                          "values": {"a": [a["start"], a["end"]], "b": [b["start"], b["end"]],
                                     "overlap_s": ov, "tolerance_s": PAD_S}})

    # ---- C02 IDENTICAL IDENTITY ----------------------------------------------------------
    by_key = {}
    for r in rows:
        if r.get("sha256"):
            by_key.setdefault(r["sha256"], []).append(r)
    for k, group in sorted(by_key.items()):
        if len(group) > 1:
            f.append({"cls": "C02", "name": "IDENTICAL IDENTITY", "severity": "red",
                      "subject": "sha256=%s" % k,
                      "detail": ("%d rows share one whole-file sha256; the index enforces "
                                 "UNIQUE(content_key) (schema.sql:44) so only ONE may be "
                                 "indexed -- the rest is DUPLICATE ROOM this tree does NOT "
                                 "write" % len(group)),
                      "evidence_paths": [g["path"] if "path" in g else g["dir"] for g in group],
                      "ranks": [g["end_source"]["rank"] if g.get("end_source") else None
                                for g in group],
                      "values": {"content_key": k, "members": [g["subject"] for g in group]}})
    for r in rows:
        if r.get("key_content_key") and r.get("sha256"):
            if r["key_content_key"] != r["sha256"]:
                f.append({"cls": "C02", "name": "IDENTITY CLAIM LIES", "severity": "red",
                          "subject": r["subject"],
                          "detail": ("key.json claims content_key=%s but the bytes hash to "
                                     "%s: identity by content is NOT what the row claims"
                                     % (r["key_content_key"], r["sha256"])),
                           "evidence_paths": [row_key_path(r), row_path(r)],
                           "ranks": [RANK_KEY, RANK_CLIP_ID],
                           "values": {"claimed": r["key_content_key"],
                                     "recomputed": r["sha256"]}})
    # the live db's OWN duplicate check
    for k, v in (db_info.get("duplicate_content_keys") or {}).items():
        f.append({"cls": "C02", "name": "DB DUPLICATE CONTENT_KEY", "severity": "red",
                  "subject": "db content_key=%s" % k,
                  "detail": "%d rows in video carry one content_key: UNIQUE is gone" % len(v),
                  "evidence_paths": [r["path"] for r in v], "ranks": [RANK_DB] * len(v),
                  "values": {"count": len(v)}})

    # ---- C03 PATH MOVED / ROW ABSENT ----------------------------------------------------
    for row in db_info.get("rows_raw") or []:
        p = row.get("path")
        if p and not Path(p).exists():
            moved = [r for r in rows if r.get("sha256") == row.get("content_key")]
            if moved:
                f.append({"cls": "C03", "name": "PATH MOVED", "severity": "red",
                          "subject": "db path=%s" % p,
                          "detail": ("the db row's path is gone but its content_key is present "
                                     "at another path: identity survived, the path did not"),
                          "evidence_paths": [p] + [m["path"] if "path" in m else m["dir"]
                                                   for m in moved],
                          "ranks": [RANK_DB, RANK_CLIP_ID],
                          "values": {"db_path": p, "now_at": [m["subject"] for m in moved]}})
            else:
                f.append({"cls": "C03", "name": "DB ROW MISSING ON DISK", "severity": "info",
                          "subject": "db path=%s" % p,
                          "detail": ("the db row names a path that is not on disk; its "
                                     "content_key %s is nowhere in this root"
                                     % (row.get("content_key") or UNKNOWN)),
                          "evidence_paths": [p], "ranks": [RANK_DB],
                          "values": {"missing": row.get("missing"),
                                     "state": row.get("state")}})

    # ---- C04 ZERO-EPOCH TRAP: COUNTED, FORMATTED NEVER --------------------------------
    for r in rows:
        for k, n in sorted((r.get("zero_epoch_fields") or {}).items()):
            if n:
                f.append({"cls": "C04", "name": "ZERO-EPOCH FIELD (not a date)",
                          "severity": "info",
                          "subject": r["subject"],
                          "detail": ("%s is literal 0 in %d box(es).  A 0 in an MP4 time field "
                                     "means 1904-01-01 and the writer of this product WRITES "
                                     "the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall "
                                     "clock.  The instrument prints the literal, not a date."
                                     % (k, n)),
                          "evidence_paths": [r["path"] if "path" in r else r["dir"]],
                          "ranks": [RANK_CONTAINER],
                          "values": {"field": k, "count": n,
                                     "as_epoch_1904_utc": "0001-01-01T00:00:00+00:00"
                                     if k else None}})

    # ---- C05 NEGATIVE OR ZERO INTERVAL --------------------------------------------------
    for r in known:
        if r["end"] <= r["start"]:
            f.append({"cls": "C05", "name": "NEGATIVE OR ZERO INTERVAL", "severity": "red",
                      "subject": r["subject"],
                      "detail": ("the chosen end (%.6f) does not come after the rank-%s start "
                                 "(%.6f, source=%s): the row is not a time interval at all"
                                 % (r["end"], (r.get("start_source") or {}).get("rank"),
                                    r["start"], (r.get("start_source") or {}).get("source"))),
                      "evidence_paths": [r["path"] if "path" in r else r["dir"]],
                      "ranks": [r["end_source"]["rank"] if r.get("end_source") else None],
                      "values": {"start": r["start"], "end": r["end"],
                                 "start_rank": (r.get("start_source") or {}).get("rank"),
                                 "end_source": (r.get("end_source") or {}).get("detail")}})

    # ---- C06 GAP: PER SUBJECT, never between clips --------------------------------------
    per_subject = {}
    for r in real:
        per_subject.setdefault(r["subject"].split(" ")[0] if False else r.get("clip_id") or
                               r["subject"], []).append(r)
    for subj, group in sorted(per_subject.items()):
        group = sorted(group, key=lambda x: x["start"])
        for a, b in zip(group, group[1:]):
            gap = b["start"] - a["end"]
            if gap > PAD_S:
                f.append({"cls": "C06", "name": "GAP", "severity": "red",
                          "subject": subj,
                          "detail": ("gate %d of a subject's own timeline is missing %.3f s "
                                     "of body (tolerance %.2f s)" % (a["clip_id"] if a.get("clip_id") else 0, gap, PAD_S)),
                          "evidence_paths": [a["path"] if "path" in a else a["dir"],
                                             b["path"] if "path" in b else b["dir"]],
                          "ranks": [RANK_CLIP_ID, RANK_CLIP_ID],
                          "values": {"previous_end": a["end"], "next_start": b["start"],
                                     "gap_s": gap}})
    # between-clip gaps are NOT a subject tiling break -> informational only
    ordered = sorted(real, key=lambda x: x["start"])
    for a, b in zip(ordered, ordered[1:]):
        gap = b["start"] - a["end"]
        if gap > PAD_S:
            f.append({"cls": "INFO-GAP", "name": "BETWEEN-CLIP GAP (informational)",
                      "severity": "info", "subject": "%s -> %s" % (a["subject"], b["subject"]),
                      "detail": ("%.3f s with no clip.  A gap between two CLIPS is not a "
                                 "finding: schema.sql:65-68 keeps the 5 s ASR window in "
                                 "segment, so the spec never asks clips to tile a subject"
                                 % gap),
                      "evidence_paths": [a["path"] if "path" in a else a["dir"],
                                         b["path"] if "path" in b else b["dir"]],
                      "ranks": [RANK_CLIP_ID, RANK_CLIP_ID],
                      "values": {"gap_s": gap}})

    # ---- C07 DECLARED vs DECODED, C08 DURATION SOURCE MISMATCH --------------------------
    for r in rows:
        cf = r.get("container") or {}
        if cf.get("refusal"):
            continue
        cont_ms = video_trak_ms(cf.get("traks"))
        r["_cont_ms"] = cont_ms
        key_ms = r.get("key_duration_ms")
        dbms = (r.get("db_row") or {}).get("duration_ms")
        if key_ms is not None and cont_ms is not None and abs(key_ms - cont_ms) > DUR_TOLERANCE_MS:
            f.append({"cls": "C07", "name": "DECLARED vs DECODED", "severity": "red",
                      "subject": r["subject"],
                      "detail": ("key.json duration_ms=%d but the moov video trak decodes "
                                 "%d ms (%d ms apart, tolerance %d ms)"
                                 % (key_ms, cont_ms, abs(key_ms - cont_ms), DUR_TOLERANCE_MS)),
                      "evidence_paths": [r["sidecars"]["key"] if "sidecars" in r else r["dir"],
                                         r["path"] if "path" in r else r["dir"]],
                      "ranks": [RANK_KEY, RANK_CONTAINER],
                      "values": {"key_ms": key_ms, "container_ms": cont_ms}})
        if dbms is not None and cont_ms is not None and abs(dbms - cont_ms) > DUR_TOLERANCE_MS:
            f.append({"cls": "C08", "name": "DURATION SOURCE MISMATCH", "severity": "red",
                      "subject": r["subject"],
                      "detail": ("db duration_ms=%d but the moov video trak decodes %d ms "
                                 "(%d ms apart, tolerance %d ms)"
                                 % (dbms, cont_ms, abs(dbms - cont_ms), DUR_TOLERANCE_MS)),
                      "evidence_paths": [r["db_row"].get("path") if r.get("db_row") else r["path"] if "path" in r else r["dir"],
                                         r["path"] if "path" in r else r["dir"]],
                      "ranks": [RANK_DB, RANK_CONTAINER],
                      "values": {"db_ms": dbms, "container_ms": cont_ms}})
        if dbms == 0 and cont_ms not in (None, 0):
            f.append({"cls": "R-DATA-QUALITY", "name": "DB DURATION ZERO FOR A READABLE CLIP",
                      "severity": "red", "subject": r["subject"],
                      "detail": ("the db declares duration_ms=0 for a container that decodes "
                                 "%d ms: a 0 is a fact about the row, not about the clip"
                                 % cont_ms),
                      "evidence_paths": [r["path"] if "path" in r else r["dir"]],
                      "ranks": [RANK_DB, RANK_CONTAINER],
                      "values": {"db_ms": 0, "container_ms": cont_ms}})
        if key_ms is not None and dbms is not None and abs(key_ms - dbms) > DUR_TOLERANCE_MS:
            f.append({"cls": "C08", "name": "KEY vs DB DURATION", "severity": "red",
                      "subject": r["subject"],
                      "detail": ("key duration_ms=%d vs db duration_ms=%d (tolerance %d ms)"
                                 % (key_ms, dbms, DUR_TOLERANCE_MS)),
                      "evidence_paths": [r["sidecars"]["key"] if "sidecars" in r else r["dir"]],
                      "ranks": [RANK_KEY, RANK_DB],
                      "values": {"key_ms": key_ms, "db_ms": dbms}})

    # ---- C09 key started_at_s vs its own clip id ----------------------------------------
    for r in rows:
        if r.get("key_started_at_s") is None or r.get("start") is None:
            continue
        d = abs(r["key_started_at_s"] - r["start"])
        if d > CLIPID_KEY_TOLERANCE_S:
            f.append({"cls": "C09", "name": "KEY START vs CLIP ID", "severity": "red",
                      "subject": r["subject"],
                      "detail": ("key started_at_s=%.6f but the directory's clip id decodes "
                                 "to %.6f (%.3f s apart, tolerance %.3f s -- layout.py:433 "
                                 "copies the clip-id start INTO the key, so any difference "
                                 "means one of the two is not the record this product wrote)"
                                 % (r["key_started_at_s"], r["start"], d,
                                    CLIPID_KEY_TOLERANCE_S)),
                      "evidence_paths": [r["sidecars"]["key"] if "sidecars" in r else r["dir"],
                                         r["dir"]],
                      "ranks": [RANK_KEY, RANK_CLIP_ID],
                      "values": {"key_started_at_s": r["key_started_at_s"],
                                 "clip_id_started_at_s": r["start"], "delta_s": d}})

    # ---- C2TRAK per-container trak durations disagree -----------------------------------
    for r in rows:
        cf = r.get("container") or {}
        if cf.get("refusal"):
            continue
        ds = [t["duration_s"] for t in cf.get("traks", []) if t.get("duration_s") is not None]
        if len(ds) >= 2 and (max(ds) - min(ds)) * 1000.0 > DUR_TOLERANCE_MS:
            f.append({"cls": "C2TRAK", "name": "TRAK DURATIONS DISAGREE", "severity": "red",
                      "subject": r["subject"],
                      "detail": ("inside ONE container the traks disagree by %.3f s "
                                 "(tolerance %d ms): a reader that takes max, min or the "
                                 "first trak gets three different clip lengths"
                                 % (max(ds) - min(ds), DUR_TOLERANCE_MS)),
                      "evidence_paths": [r["path"] if "path" in r else r["dir"]],
                      "ranks": [RANK_CONTAINER],
                      "values": {"trak_durations_s": [round(x, 6) for x in ds],
                                 "handlers": [t.get("handler") for t in cf["traks"]],
                                 "max_minus_min_s": max(ds) - min(ds)}})

    # ---- every container that refused: named, with its first cause ----------------------
    for r in rows:
        rf = r.get("container_refusal") or {}
        if rf:
            f.append({"cls": "REFUSAL", "name": "REFUSED TO PRODUCE A DURATION",
                      "severity": "red", "subject": r["subject"],
                      # first cause -> what it therefore made UNKNOWN.  The first code is the
                      # one to fix; the terminal names what stayed UNKNOWN.
                      "detail": "%s: %s -> %s: %s" % (rf.get("code"), rf.get("detail"),
                                                      rf.get("terminal_code"),
                                                      rf.get("terminal_detail")),
                      "evidence_paths": [r["path"] if "path" in r else r["dir"]],
                      "ranks": [RANK_CONTAINER],
                      "values": {"code": rf.get("code"),
                                 "terminal": rf.get("terminal_code")}})
        ke = r.get("key_error")
        if ke and not ke.startswith("None") and r.get("key") is None:
            # a refusal word is not a code.  layout.py refuses a v2 key with this exact text,
            # so the code is read off the measured cause instead of being guessed.
            kcode = "R-VERSION" if "layout_version=2" in ke else "R-KEY-UNREADABLE"
            f.append({"cls": "REFUSAL", "name": "REFUSED TO READ THE KEY", "severity": "red",
                      "subject": r["subject"], "detail": "%s: %s" % (kcode, ke),
                      "evidence_paths": [r["dir"]] if "dir" in r else [r["path"]],
                      "ranks": [RANK_KEY], "values": {"code": kcode}})

    # ---- R-WRONG-DIR: the key names a clip_id that is NOT this directory ------------------
    # layout.py classify() refuses the whole key when its clip_id does not match the
    # directory (read_key:331-353), so the directory keeps rank 1 and the claim of the key
    # is a REFUSAL, not a second source.  Without this branch the clip_id of the key wins
    # over the directory name in the report and nothing says the key was not trusted.
    for r in rows:
        k = r.get("key") or {}
        kid = k.get("clip_id")
        if kid and r.get("clip_id") and kid != r["clip_id"]:
            f.append({"cls": "REFUSAL", "name": "KEY NAMES ANOTHER DIRECTORY",
                      "severity": "red", "subject": r["subject"],
                      "detail": ("R-WRONG-DIR: key.json claims clip_id=%s but this directory is "
                                 "%s, so layout.py refuses the key and the clip_id of the key "
                                 "does NOT override the directory (the directory stays rank 1)"
                                 % (kid, r["clip_id"])),
                      "evidence_paths": [row_key_path(r), row_path(r)],
                      "ranks": [RANK_KEY, RANK_CLIP_ID],
                      "values": {"code": "R-WRONG-DIR", "claimed_clip_id": kid,
                                 "dir_clip_id": r["clip_id"]}})
    return f


def emit_r_db_rows_absent(rows, db_info, f):
    """A clip on disk with no db row at all: a row the index never got."""
    for r in rows:
        if r.get("kind") != "clip":
            continue
        if r.get("db_row"):
            continue
        if r.get("verdict") not in ("committed", "partial-committed", "missing-media"):
            continue
        p = r.get("media_path")
        if not p or not Path(p).exists():
            continue
        f.append({"cls": "C03", "name": "DB ROW ABSENT", "severity": "red",
                  "subject": r["subject"],
                  "detail": ("a %s clip is on disk with no video row naming it: the index "
                             "never saw it" % r["verdict"]),
                  "evidence_paths": [r["dir"]], "ranks": [RANK_CLIP_ID], "values": {}})
    return f


# =============================== the run ====================================================

def walk_foreign(root, clip_dirs):
    """Container-eligible files that are NOT inside a clip directory.

    An imported library file (no copies of the videos, no frame dumps -- the brief's rule) lives
    outside the clip tree; it is still part of the on-disk search and still gets a timeline row.
    """
    out = []
    base = Path(root).resolve()
    for dirpath, dirnames, filenames in os.walk(base):
        here = str(Path(dirpath).resolve())
        if here in clip_dirs:
            dirnames[:] = []            # a clip directory: iter_clips already owns it
            continue
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1].lower()
            if ext in CONTAINER_EXTS:
                out.append(Path(dirpath) / fname)
    return sorted(out)


def fmt_ts(v):
    # A timestamp prints as an ISO-8601 instant, or the literal UNKNOWN.  Never 0.
    if v is None:
        return UNKNOWN
    try:
        return iso(float(v))
    except (TypeError, ValueError):
        return str(v)


def _src_field(row, field):
    s = row.get(field + "_source")
    if isinstance(s, dict):
        return s
    return {"source": "UNKNOWN", "rank": None, "evidence_path": UNKNOWN}


def source_of(row, field):
    return _src_field(row, field).get("source", UNKNOWN)


def rank_of(row, field):
    r = _src_field(row, field).get("rank")
    return ("--" if r is None else str(r)) + ("/" + str(RANK_NAME.get(r, "?")) if r in RANK_NAME else "")


def refuse(code, message):
    # A run refusal: exit 2, no report, one line naming the first cause.
    sys.stderr.write("REFUSED %s: %s\n" % (code, message))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="ods1",
        description="ODS arm A/B -- the on-disk search instrument (design THE-INSTRUMENT.md run "
                    "on a synthetic store).  Reads nodes and bytes; no pixels, no streams.")
    ap.add_argument("--layout", required=True, help="path to the product's src/storage/layout.py")
    ap.add_argument("--root", required=True, help="the store root (the dir that holds clips/)")
    ap.add_argument("--db", default=None, help="index sqlite (default: found under --root)")
    ap.add_argument("--manifest", default=None, help="the fixture manifest to check expectations "
                                                     "against")
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--arm", default="a", choices=["a", "b"],
                    help="a = the synthetic store (the guard below applies); b = the AUTHORISED read of the product's own clips (guard becomes a LOUD WARN)")
    ap.add_argument("--expect-store", default=None,
                    help="which manifest store to compare this run against")
    args = ap.parse_args(argv)

    layout_p = Path(args.layout).resolve()
    repo_root = layout_p.parent.parent.parent   # src/storage/layout.py -> repo root
    root = Path(args.root).resolve()
    # ---- the run guard: arm A must never read the product's own clips -------------------
    # ods1.py (ARM A) REFUSES any root inside the repo.  ARM B is the AUTHORISED read of the
    # product tree, so the same guard becomes a LOUD WARN recorded in the output -- never
    # silent.  This is the only place the two arms differ besides the report title.
    guard_note = ""
    if getattr(args, "arm", "a") == "b":
        if root == repo_root or root.is_relative_to(repo_root) or repo_root.is_relative_to(root):
            guard_note = ("E-ROOT-INSIDE-REPO NOT APPLIED (--arm b, authorised product-tree read):"
                          " --root %s is inside the repo %s.  The arms that must not read this "
                          "tree are the ARM A ones; ARM B is exactly that authorised read."
                          % (root, repo_root))
        else:
            guard_note = ("E-ROOT-INSIDE-REPO not applicable: --root %s is outside the repo %s."
                          % (root, repo_root))
    elif root == repo_root or root.is_relative_to(repo_root):
        return refuse("E-ROOT-INSIDE-REPO", "--root %s is inside the repo %s.  Arm A NEVER reads "
                      "the product tree: the real clips' clocks were rewritten by other lanes."
                      % (root, repo_root))
    if repo_root.is_relative_to(root):
        return refuse("E-ROOT-COVERS-REPO", "--root %s contains the whole repo %s"
                      % (root, repo_root))
    if not root.is_dir():
        return refuse("E-ROOT-MISSING", "--root %s is not a directory" % root)

    L = load_layout(layout_p)
    started = iso(time.time())
    errors = []
    clips = list(L.iter_clips(root, errors))
    if not clips:
        return refuse("E-NO-CLIPS", "%s holds no clip directories under %s (layout.py's own walk "
                      "found none)" % (root, L.clips_root(root)))


    # ---- the db ---------------------------------------------------------------------------
    db_candidates = [Path(args.db)] if args.db else list(find_index_db(root))
    db_info = None
    db_path = None
    for cand in db_candidates:
        if not cand or not Path(cand).is_file():
            continue
        info = read_db_dups(cand)
        if info.get("present"):
            db_info, db_path = info, Path(cand)
            break
    if db_info is None:
        db_path = db_candidates[0] if db_candidates else None
        db_info = {"present": False, "rows": [], "rows_raw": [],
                   "duplicate_content_keys": {}, "tables": []}
    db_rows = db_info["rows_raw"]
    # one index of every db row by the FILE it names, and one by CONTENT (identity, never path)
    db_by_path = {}
    db_by_key = {}
    for r in db_rows:
        if r.get("path"):
            db_by_path[str(Path(r["path"]))] = r
        if r.get("content_key"):
            db_by_key.setdefault(r["content_key"], []).append(r)

    # ---- the walk --------------------------------------------------------------------------
    rows = []
    for c in clips:
        rows.append(clip_timeline(analyse_clip(L, c, db_by_path)))
    clip_dirs = set(str(Path(c.path).resolve()) for c in clips)
    foreign = walk_foreign(root, clip_dirs)
    for f in foreign:
        # ONE read of the bytes serves TWO purposes: the identity lookup of the db row below
        # and the C02 identical-identity census.  A foreign row therefore carries its sha256,
        # exactly like a clip row -- without it, two files with the same bytes on disk are
        # invisible to the one check that exists precisely to find them.
        try:
            fsha, fsha_error = sha256_file_any(f), None
        except Exception as exc:
            fsha, fsha_error = None, "%s: %s" % (type(exc).__name__, exc)
        db_row = db_by_path.get(str(Path(f))) or (
            (db_by_key.get(fsha) or [None])[0] if fsha else None)
        rows.append(foreign_timeline(f, db_row, fsha, fsha_error))
    skipped_non_clip_dirs = []
    base = L.clips_root(root)
    if base.is_dir():
        for ym in sorted(base.glob("*/*/*")):
            if not ym.is_dir():
                continue
            for d in sorted(p for p in ym.iterdir() if p.is_dir()):
                if not L.CLIP_ID_RE.match(d.name):
                    skipped_non_clip_dirs.append(str(d))
    foreign_skipped = len(skipped_non_clip_dirs)

    # ---- the findings -----------------------------------------------------------------------
    findings = find_contradictions(rows, db_info, L, root)
    findings = emit_r_db_rows_absent(rows, db_info, findings)
    red = [f for f in findings if f.get("severity") == "red"]
    refusals = [f for f in findings if f["cls"] == "REFUSAL"]
    groups = {}
    for f in findings:
        groups.setdefault(f["cls"], []).append(f)
    order = {"C01":1,"C02":2,"C03":3,"C04":4,"C05":5,"C06":6,"C07":7,"C08":8,"C09":9,
            "C2TRAK":10,"R-DATA-QUALITY":11,"REFUSAL":12,"INFO-GAP":13}
    findings.sort(key=lambda x: (order.get(x["cls"], 99), x["subject"]))

    # ---- the self-audit (this instrument's own invariants) ---------------------------------
    audit = []
    def inv(name, ok, detail):
        audit.append({"name": name, "ok": bool(ok), "detail": detail})

    inv("rows_emitted_equals_visited",
        len(rows) == len(clips) + len(foreign),
        "rows=%d clips_visited=%d foreign_visited=%d" % (len(rows), len(clips), len(foreign)))
    seen_rows = [(r.get("start"), r.get("end"), r.get("subject")) for r in rows]
    inv("no_duplicate_rows", len(seen_rows) == len(set(map(str, seen_rows))),
        "%d rows, %d distinct" % (len(seen_rows), len(set(map(str, seen_rows)))))
    zero_dates = [r["subject"] for r in rows if r.get("mvhd_creation_time_iso")]
    inv("zero_epoch_fields_formatted_as_dates", len(zero_dates) == 0,
        "%d row(s) printed a DATE derived from an mp4 stamp; the writer of this tree writes "
        "the literal 0 (mp4_writer.cpp:257, :272, :293)" % len(zero_dates))
    unknown_printed = [r["subject"] for r in rows
                       if r.get("start") is None or r.get("end") is None]
    # the invariant tests the PRINTER, not a predicate that is false by construction: an
    # absent value is a Python None on the row and prints as the literal word UNKNOWN.
    inv("unknown_prints_as_the_literal_word",
        all(fmt_ts(r.get(k)) == UNKNOWN for r in rows for k in ("start", "end")
            if r.get(k) is None),
        "%d row(s) carry at least one absent value; each prints 'UNKNOWN', never 0" %
        len(unknown_printed))
    no_zero_as_unknown = [r["subject"] for r in rows
                          if (r.get("start") == 0) or (r.get("end") == 0)]
    inv("zero_is_never_an_absent_value", len(no_zero_as_unknown) == 0,
        "%d row(s) use the number 0 as a value" % len(no_zero_as_unknown))
    clipid_starts = [r for r in rows if r.get("start") is not None and r.get("kind") == "clip"]
    inv("clip_start_is_rank_1_when_present",
        all(r.get("start_source", {}).get("rank") == RANK_CLIP_ID
            for r in clipid_starts if r.get("start") is not None),
        "%d of %d clip rows started from the CLIP ID (rank 1), the only source that ranks "
        "above the key" % (sum(1 for r in clipid_starts
                               if r.get("start_source", {}).get("rank") == RANK_CLIP_ID),
                           len(clipid_starts)))
    verdicts = {}
    for r in rows:
        verdicts[r.get("verdict", "?")] = verdicts.get(r.get("verdict", "?"), 0) + 1
    rows_with_keys = [r for r in rows if r.get("key_content_key")]
    verified = [r for r in rows_with_keys if r.get("sha256")]
    inv("every_identity_claim_was_recomputed", len(rows_with_keys) == len(verified),
        "identity claims found=%d, recomputed against the bytes=%d" %
        (len(rows_with_keys), len(verified)))
    audit_red = [a for a in audit if not a["ok"]]


    # ---- the report (markdown, and the machine-readable twin) -------------------------------
    BT = chr(96)
    lines = []
    A = lines.append
    A("# ODS-1 ARM %s -- the on-disk search run on a %s store"
      % ("A" if getattr(args, "arm", "a") == "a" else "B",
         "SYNTHETIC" if getattr(args, "arm", "a") == "a" else
         "REAL (the product tree, READ ONLY, clocks NOT trusted)"))
    A("")
    A("DUPLICATE ROOM POLICY: NONE WRITTEN IN THIS TREE.")
    A("Nothing under the root of this run was created, renamed, linked, copied or removed. Arm A")
    A("does not repair, does not dedupe, and does not take the " + BT + "right" + BT + " side of a")
    A("contradiction -- it prints the sides and ranks them. Every number below was measured at run")
    A("time; the synthetic fixture values are CHOSEN test inputs, never measurements."
      if getattr(args, "arm", "a") == "a" else
      "every number below is a MEASUREMENT of bytes on disk at the run window above.")
    if guard_note:
        A("")
        A("GUARD: " + guard_note)
    A("")
    A("| run | value |")
    A("|---|---|")
    A("| instrument | ods1.py, --layout %s --root %s |" % (args.layout, str(root)))
    A("| store root | %s%s%s |" % (BT, root, BT))
    A("| index db | %s%s%s |" % (BT, str(db_path) if db_path else "UNKNOWN (no *.db under the root)", BT))
    A("| run started | %s |" % started)
    A("| layout.py sha256 | %s |" % hashlib.sha256(Path(args.layout).read_bytes()).hexdigest())
    A("| clips visited (layout.py's own walk) | %d |" % len(clips))
    A("| foreign container files visited | %d |" % len(foreign))
    A("| rows emitted | %d |" % len(rows))
    A("| db video rows | %d |" % len(db_rows))
    A("| db duplicate content_keys | %d |" % len(db_info["duplicate_content_keys"]))
    A("| findings | %d red, %d informational |" % (len(red), len(findings) - len(red)))
    A("| refusals to produce a duration | %d |" % len(refusals))
    A("| self-audit invariants | %d green, %d RED |" % (len(audit) - len(audit_red), len(audit_red)))
    A("| exit code | %d |" % (0 if not red and not audit_red else 1))
    A("")
    A("## HOW A SOURCE RANK WAS CHOSEN (the priority contract)")
    A("")
    A("%s%s%s" % (BT, RANK_LEGEND.replace("    ", ""), BT))
    A("")
    A("* start = the CLIP ID (rank 1), decoded by parse_clip_id (layout.py:139). Nothing outranks")
    A("  the clip id, and no other source can move a start.")
    A("* end = the highest-rank source that carries one: key ended_at_s (2) > db duration_ms added")
    A("  to that start (3) > container/moov (4) > mtime-derived (5).")
    A("* **An absent value prints UNKNOWN. It is never 0 and it is never a guess.**")
    A("* A REFUSED container has no duration: it prints UNKNOWN, never 0.")
    A("")
    A("Tolerances (each with where it came from):")
    A("")
    A("| tolerance | value | basis |")
    A("|---|---|---|")
    A("| interval overlap (C01) | %.2f s | READ specs/02-asr.md:165 PAD_S 0.10 |" % PAD_S)
    A("| duration agreement | %d ms | chosen by this lane (a rounding allowance) |" % DUR_TOLERANCE_MS)
    A("| key start vs clip id (C09) | %.3f s | READ layout.py:433 -- the key COPIES the clip id |" % CLIPID_KEY_TOLERANCE_S)
    A("| mp4 epoch offset | -2082844800 s | COMPUTED here: datetime(1904,1,1,utc).timestamp() |")
    A("")
    A("NOT MEASURED BY THIS INSTRUMENT: no pixel is read, no SPS/PPS is parsed, no audio or video")
    A("stream is decoded, no image is opened, no audio device is opened, nothing is written.")
    A("")
    A("## THE SANITY TRAPS, RUN")
    A("")
    A("1. **Every mvhd/tkhd/mdhd stamp on this writer is the literal 0** (mp4_writer.cpp:257, :272,")
    A("   :293). The instrument COUNTS those fields and prints the count; it never converts a 0")
    A("   into a date. Zero-epoch fields formatted as dates in this run: **%d**." % len(zero_dates))
    blk = {}
    for r in rows:
        for k, n in (r.get("zero_epoch_fields") or {}).items():
            blk[k] = blk.get(k, 0) + n
    A("   Field census over this store: %s." % (", ".join("%s=%d" % kv for kv in sorted(blk.items()))
                                                  or "none found"))
    A("2. **Missing means UNKNOWN.** %d row(s) carry at least one absent value in this run; each")
    A("   prints the literal word UNKNOWN, and the invariant zero_is_never_an_absent_value stays")
    A("   green.")

    A("")
    A("## THE TIMELINE (every row carries its evidence path and its ranks)")
    A("")
    A("start is the rank-1 instant. end came from the highest rank that carried one. The last two")
    A("columns name WHICH source produced the end and WHAT rank it had.")
    A("")
    A("| # | kind | verdict | start (UTC) | start rank | end (UTC) | end source | end rank | clip id / file | evidence path |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        A("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            i, r.get("kind"), r.get("verdict"),
            fmt_ts(r.get("start")), rank_of(r, "start"),
            fmt_ts(r.get("end")), source_of(r, "end"), rank_of(r, "end"),
            r.get("clip_id") or Path(r["path"]).name,
            r["path"] if "path" in r else r["dir"]))
    A("")
    A("## THE CONTRADICTIONS FOUND, BY CLASS")
    A("")
    if not findings:
        A("NONE. The store is CLEAN: no overlap, no duplicate identity, no duration disagreement,")
        A("no key-vs-clip-id disagreement, no trak disagreement, no refusal.")
    groups = {}
    for f in findings:
        groups.setdefault(f["cls"], []).append(f)
    for cls in sorted(groups, key=lambda c: order.get(c, 99)):
        group = groups[cls]
        name = group[0]["name"]
        A("### %s -- %s (%d)" % (cls, name, len(group)))
        A("")
        for f in group:
            A("* **%s** -- %s" % (f["subject"], f["detail"]))
            A("  * evidence: %s (ranks %s)" % (
                ", ".join(str(e) for e in f["evidence_paths"]),
                ", ".join(str(x) for x in f["ranks"] if x is not None) or "UNKNOWN"))
        A("")
    A("## ROWS THAT REFUSED TO GIVE A DURATION (a refusal is not a zero)")
    A("")
    if not refusals:
        A("NONE. Every container in this store yielded a duration.")
    for f in refusals:
        A("* %s -- %s (evidence: %s)" % (f["subject"], f["detail"], f["evidence_paths"][0]))
    A("")
    A("## THE DB, AS IT IS")
    A("")
    A("* tables found: %s" % (", ".join(db_info["tables"]) or "UNKNOWN"))
    A("* video rows: %d" % len(db_rows))
    A("* duplicate content_key in the live db: **%d** (schema.sql:44 declares it UNIQUE)" %
      len(db_info["duplicate_content_keys"]))
    A("* rows whose declared path is absent from disk: %d" %
      sum(1 for r in db_rows if r.get("path") and not Path(r["path"]).exists()))
    A("")
    A("## SELF-AUDIT -- THIS INSTRUMENT'S OWN INVARIANTS")
    A("")
    A("| invariant | state | detail |")
    A("|---|---|---|")
    for a in audit:
        A("| %s | %s | %s |" % (a["name"], "GREEN" if a["ok"] else "RED", a["detail"]))
    A("")
    A("## CENSUS")
    A("")
    A("| bucket | count |")
    A("|---|---|")
    for k in sorted(verdicts, key=lambda x: str(x)):
        A("| verdict %s | %d |" % (k, verdicts[k]))
    A("| non-clip-id directories skipped under clips/ | %d |" % foreign_skipped)
    A("| db rows | %d |" % len(db_rows))
    A("| db duplicate content_keys | %d |" % len(db_info["duplicate_content_keys"]))
    A("")
    A("## WHAT THIS RUN DID NOT VERIFY (say it, do not fill it in)")
    A("")
    A("* The PAD_S 0.10 overlap tolerance is READ from specs/02-asr.md:165, where it is defined")
    A("  for ASR segment padding. The spec does not state a tolerance for two CLIP intervals;")
    A("  TO-BE-ANSWERED-BY-OWNER.md carries the question.")
    A("* No transcript, segment or subject rows exist in this arm, so C06 (a per-subject tiling")
    A("  gap) could not be exercised -- schema.sql:65-68 keeps the window in segment, not here.")
    A("* A foreign file's duration has no source besides the db and its own moov; no key.json sits")
    A("  next to an imported library file.")
    A("* Whether an imported moov carries a usable creation_time is UNKNOWN: the only files this")
    A("  product writes carry the literal 0, and no foreign file was measured on this box.")
    A("")
    A("PROVENANCE: " + ("values under the synthetic store are CHOSEN test inputs; every other"
                       "number was measured by this run." if getattr(args, "arm", "a") == "a" else
                       "every value below was MEASURED from the bytes on disk at the run window"
                       "above; the capturing lane wrote the clocks and this run reads what is"
                       "THERE now.") + " The layout.py sha256 above names the exact revision")
    A("every disk fact was routed through.")


    # ---- expectations from the fixture manifest (if the caller passed one) -----------------
    exp_store = args.expect_store
    expectation = None
    root_mismatch = None
    if args.manifest:
        man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        stores = man.get("stores") or {}
        if isinstance(stores, list):
            stores = dict((s.get("store") or s.get("id") or "?", s) for s in stores)
        keys = list(stores.keys())
        if not exp_store:
            exp_store = keys[0] if len(keys) == 1 else None
        if exp_store is None:
            sys.stderr.write("NOTE: the manifest carries %d stores (%s); pass --expect-store "
                             "<id> to compare against one\\n" % (len(keys), ", ".join(keys)))
        else:
            expectation = {"store": exp_store, "expect": stores[exp_store].get("expect", {}),
                          "notes": stores[exp_store].get("notes", [])}
            mr = stores[exp_store].get("root")
            if mr and Path(mr).resolve() != root:
                root_mismatch = (str(mr), str(root))
    # the fixture names (A001, A900, legacy-...mp4) are CHOSEN test inputs; findings speak in clip
    # ids and paths. Build the alias map so an expectation named A012 can match the finding that
    # names 20261009T120138Z-0012 -- and never the other way round.
    name_alias = {}
    if expectation:
        for grp in ("clips", "foreign"):
            for e in (stores[exp_store].get(grp) or []):
                if not isinstance(e, dict):
                    continue
                nm = str(e.get("name") or "")
                if not nm:
                    continue
                name_alias.setdefault(nm, set()).update(str(e.get(k) or "").strip()
                                                      for k in ("clip_id", "path", "subject"))
        name_alias = dict((k, sorted(v for v in vs if v)) for k, vs in name_alias.items())
    checks = []
    if expectation:
        def _tok(entry):
            if isinstance(entry, dict):
                return str(entry.get("name") or entry.get("clip_id") or entry.get("class") or "")
            return str(entry)

        def _aliases(tok):
            out = [tok]
            for a in (name_alias.get(tok) or []):
                if a and a not in out:
                    out.append(a)
            return out

        for cls in sorted(expectation["expect"], key=lambda c: order.get(c, 99)):
            want = expectation["expect"][cls] or []
            if cls == "REFUSAL":
                got = [x for x in findings if x["cls"] == "REFUSAL"]
                for entry in want:
                    tok = _tok(entry)
                    code = entry.get("class") if isinstance(entry, dict) else None
                    toks = _aliases(tok)
                    hit = any(any(t in (x["subject"] + " " + x["detail"] + " " +
                                  " ".join(x["evidence_paths"])) for t in toks) and
                              (not code or code in x["detail"]) for x in got)
                    checks.append({"store": exp_store, "class": cls, "expected": tok,
                                   "actual": "%d REFUSAL finding(s) in this run" % len(got),
                                   "ok": hit})
                continue
            if cls in ("FINISH", "DISCARD", "ORPHAN", "MISSING-MEDIA", "COMMITTED"):
                for entry in want:
                    tok = _tok(entry)
                    toks = _aliases(tok)
                    hit = any(any(n and (n in (r.get("clip_id") or "") or
                                  n in str(r.get("path") or "")) for n in toks)
                              for r in rows)
                    checks.append({"store": exp_store, "class": cls, "expected": tok,
                                   "actual": "%d row(s) carry that token"
                                   % sum(1 for r in rows if any(n and n in str(r.get("path") or "")
                                                               for n in toks)),
                                   "ok": hit})
                continue
            got = [x for x in findings if x["cls"] == cls]
            if not want:
                # an empty expectation means NO RED finding of this class
                nred = len([x for x in got if x["severity"] == "red"])
                checks.append({"store": exp_store, "class": cls, "expected": "NONE",
                               "actual": "%d finding(s), %d red" % (len(got), nred),
                               "ok": nred == 0})
                continue
            blobparts = []
            for x in got:
                blobparts.append(x["subject"] + " " + x["detail"])
                blobparts.extend(x["evidence_paths"])
                blobparts.extend(json.dumps(x.get("values") or {}, default=str))
            blob = " || ".join(str(x) for x in blobparts)
            for entry in want:
                tok = _tok(entry)
                toks = _aliases(tok)
                checks.append({"store": exp_store, "class": cls, "expected": tok,
                               "actual": "%d %s finding(s)" % (len(got), cls),
                               "ok": any(t and t in blob for t in toks)})

    failed_checks = [c for c in checks if not c["ok"]]


    # ---- the machine-readable twin --------------------------------------------------------
    report = {
        "instrument": "ods1.py",
        "arm": ("A (synthetic store, no device, no build, no capture)" if getattr(args, "arm", "a") == "a"
                else "B (READ of the store on disk under H:, no device, no build, no capture, no harm)"),
        "guard_note": guard_note,
        "run_started_utc": started,
        "run_finished_utc": iso(time.time()),
        "duplicate_room_policy": "NONE WRITTEN IN THIS TREE",
        "root": str(root),
        "layout_py": str(layout_p),
        "layout_py_sha256": hashlib.sha256(layout_p.read_bytes()).hexdigest(),
        "db": None if not db_path else str(db_path),
        "reads": {
            "pixels": False, "sps_pps": False, "streams_decoded": False,
            "audio_device_opened": False, "bytes_written_into_root": 0,
        },
        "tolerances": {
            "PAD_S": PAD_S, "PAD_S_basis": "READ specs/02-asr.md:165",
            "DUR_TOLERANCE_MS": DUR_TOLERANCE_MS,
            "DUR_TOLERANCE_MS_basis": "chosen by this lane",
            "CLIPID_KEY_TOLERANCE_S": CLIPID_KEY_TOLERANCE_S,
            "CLIPID_KEY_TOLERANCE_S_basis": "READ layout.py:433 (the key copies the clip id)",
            "mp4_epoch_offset_s": MP4_EPOCH_UNIX_S,
            "mp4_epoch_offset_s_basis": "COMPUTED here: datetime(1904,1,1,utc).timestamp()",
        },
        "counts": {"clips_visited": len(clips), "foreign_visited": len(foreign),
                   "rows_emitted": len(rows), "db_rows": len(db_rows),
                   "db_duplicate_content_keys": len(db_info["duplicate_content_keys"]),
                   "findings_red": len(red), "findings_info": len(findings) - len(red),
                   "refusals": len(refusals),
                   "audit_green": len(audit) - len(audit_red), "audit_red": len(audit_red)},
        "verdicts": verdicts,
        "zero_epoch_fields_formatted_as_dates": len(zero_dates),
        "zero_epoch_field_census": blk,
        "rows": rows,
        "findings": findings,
        "self_audit": audit,
        "expectation_checks": checks,
        "expectation_checks_failed": len(failed_checks),
        "expectation_root_mismatch": root_mismatch,
        "expectation_notes": expectation["notes"] if expectation else [],
        "layout_errors": [str(e) for e in errors],
        "exit_code": None,
    }
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(report, indent=1, ensure_ascii=True) + "\n",
                                        encoding="utf-8")
    if args.out_md:
        md = "\n".join(lines) + "\n"
        if checks:
            md += "\n## EXPECTED vs ACTUAL (this run against the fixture manifest)\n\n"
            md += "| store | class | expected | actual | state |\n|---|---|---|---|---|\n"
            for c in checks:
                md += "| %s | %s | %s | %s | %s |\n" % (c["store"], c["class"], c["expected"],
                                                        c["actual"],
                                                        "OK" if c["ok"] else "MISSING")
            md += "\n%d expectation(s), %d MISSING.  A MISSING line is a contradiction the\n" \
                  "instrument did not catch, or a fixture expectation this run disagrees with --\n" \
                  "either way it is a finding, and it is printed, never hidden.\n" % \
                  (len(checks), len(failed_checks))
            if root_mismatch:
                md += "\nNOTE: the manifest's %s names root %s, this run used %s.\n" % \
                      (exp_store, root_mismatch[0], root_mismatch[1])
        Path(args.out_md).write_text(md, encoding="utf-8")

    # ---- the exit code is the contract ------------------------------------------------------
    if audit_red:
        code = 3
    elif red or failed_checks:
        code = 1
    else:
        code = 0
    report["exit_code"] = code
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(report, indent=1, ensure_ascii=True) + "\n",
                                        encoding="utf-8")
    if not args.quiet:
        print("ODS-1 ARM %s  root=%s" % (getattr(args, "arm", "a").upper(), root))
        print("  clips=%d foreign=%d rows=%d db_rows=%d" %
              (len(clips), len(foreign), len(rows), len(db_rows)))
        print("  findings: red=%d info=%d refusals=%d" %
              (len(red), len(findings) - len(red), len(refusals)))
        for cls in sorted(groups, key=lambda c: order.get(c, 99)):
            print("    %-9s %d" % (cls, len(groups[cls])))
        print("  self-audit: %d green, %d RED" % (len(audit) - len(audit_red), len(audit_red)))
        for a in audit:
            print("    [%s] %s -- %s" % ("ok" if a["ok"] else "RED", a["name"], a["detail"]))
        if checks:
            print("  expectations: %d checked, %d MISSING" % (len(checks), len(failed_checks)))
            for c in failed_checks:
                print("    MISSING %s %s (actual: %s)" % (c["class"], c["expected"], c["actual"]))
        print("  exit=%d (%s)" % (code, {0: "clean", 1: "findings", 2: "run refusal",
                                          3: "self-audit RED"}[code]))
    return code


if __name__ == "__main__":
    sys.exit(main())












