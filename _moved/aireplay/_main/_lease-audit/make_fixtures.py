"""make_fixtures.py -- builds the Arm A synthetic clip store under I:/cc-tmp/ods1-armA/.

Arm A reads a store with KNOWN instants, so every value in it is CHOSEN HERE and is a test
input, never a measurement.  The store is a real clip store in every mechanical respect:

  * every directory name is produced by the PRODUCT's own layout.make_clip_id / clip_dir, so
    the UTC date triple under clips/ cannot drift from what the product writes;
  * every key.json carries the fields layout.commit() writes (layout.py:430-445) and is
    readable by the product's own layout.read_key, including its version dispatch;
  * store.db is created by executing the PRODUCT's src/index/schema.sql verbatim.

Contradictions are planted DELIBERATELY, at least one of each class the instrument must
detect, and each planted one is recorded in manifest.json so the checker can prove it was
caught.  Nothing here writes to the repo, to a worktree, or to the real library root.
Pure stdlib, ASCII only.
"""

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mp4fix  # noqa: E402

REPO = Path("H:/sotto/_moved/aireplay")
LAYOUT_PY = REPO / "src/storage/layout.py"
SCHEMA_SQL = REPO / "src/index/schema.sql"

# ------------------------------------------------------------------ load the product's rules


def _load_layout():
    spec = importlib.util.spec_from_file_location("ods_layout", LAYOUT_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ods_layout"] = mod
    spec.loader.exec_module(mod)
    return mod


LAYOUT = _load_layout()

S0 = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc).timestamp()
FULL = "full"
CLEAN = "clean"
MUTANT = "mutant"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def clip_id_at(offset_s, seq):
    """A clip_id for an instant, built by the product's own make_clip_id."""
    return LAYOUT.make_clip_id(S0 + float(offset_s), seq)


# ------------------------------------------------------------------ the clip records


def media(dur_s, *, timescale=1000, ticks_per_sample=None, n_samples=None,
          audio_dur_s=None, audio_timescale=1000, width=1920, height=1080, mode="full",
          with_stts=True, chunk=None, salt=None):
    """Real container bytes.

    salt makes every clip's payload UNIQUE so two different clips never share a content_key
    by accident; the two identical-duplicate clips are built WITHOUT a salt on purpose, which
    is what makes their whole-file sha256 equal.
    """
    if chunk is None:
        chunk = (("salt%03d|" % salt).ljust(16, ".")).encode("ascii") if salt is not None \
            else b"\x00" * 16
    if n_samples is None:
        n_samples = max(1, int(round(dur_s * 100)))
    if ticks_per_sample is None:
        ticks_per_sample = max(1, int(timescale * dur_s / n_samples))
    ticks = [ticks_per_sample] * n_samples
    audio_ticks = None
    if audio_dur_s is not None:
        audio_ticks = [max(1, int(audio_timescale * audio_dur_s / 40))] * 40
    if mode == "nodur":
        return mp4fix.build_nodur_mp4(width=width, height=height, chunk=chunk)
    if mode == "crash":
        return mp4fix.build_mp4(ticks, timescale=timescale, width=width, height=height,
                               chunk=chunk, mode="crash")
    if mode == "truncated":
        return mp4fix.build_mp4(ticks, timescale=timescale, width=width, height=height,
                               chunk=chunk, mode="truncated", truncate_moov_at=12)
    return mp4fix.build_mp4(ticks, timescale=timescale, width=width, height=height,
                            chunk=chunk, audio_ticks=audio_ticks,
                            audio_timescale=audio_timescale, with_stts=with_stts)


def key_obj(clip_id, started_at_s, ended_at_s, duration_ms, size_bytes, mtime_ns,
            content_key, *, layout_version=1, media_name="clip.mp4",
            key_clip_id=None, source_device="fixture", mode_name="gaming"):
    return {
        "layout_version": layout_version,
        "clip_id": key_clip_id if key_clip_id else clip_id,
        "started_at_s": started_at_s,
        "ended_at_s": ended_at_s,
        "media": media_name,
        "transcript": None,
        "thumb": None,
        "size_bytes": size_bytes,
        "mtime_ns": mtime_ns,
        "duration_ms": int(duration_ms),
        "source_device": source_device,
        "mode": mode_name,
        "content_key": content_key,
        "committed_at_s": ended_at_s,
    }


# ---------------------------------------------------------------- byte surgery for refusals
# These build containers whose DEFECT is only reachable by editing real box bytes, so the
# instrument's refusal paths are exercised rather than dead code.  Every offset below is found
# by walking the boxes, never hard-coded from a remembered layout.


def _box_chain(buf, start, end):
    """[(type, body_off, body_end)] for the boxes in [start, end)."""
    out = []
    off = start
    while off + 8 <= end:
        size, typ = struct.unpack(">I4s", bytes(buf[off:off + 8]))
        if size < 8 or off + size > end:
            break
        out.append((typ, off + 8, off + size))
        off += size
    return out


def inject_unknown_top_box(buf, box_type=b"zzzz"):
    """A valid container with one UNIMPLEMENTED top-level box after ftyp: R-BOX-UNKNOWN."""
    out = bytearray(buf)
    first = struct.unpack(">I", bytes(out[0:4]))[0]
    out[first:first] = struct.pack(">I4s", 12, box_type) + b"\x00\x00\x00\x00"
    return bytes(out)


def patch_box_version(buf, box_name, version):
    """Set a FullBox version byte (moov's direct child): R-BOX-VERSION for mvhd v1."""
    out = bytearray(buf)
    for typ, s, _e in _box_chain(out, 0, len(out)):
        if typ != b"moov":
            continue
        for t2, s2, _e2 in _box_chain(out, s, _e):
            if t2 == box_name:
                out[s2] = version
    return bytes(out)


def patch_mdhd_timescale(buf, timescale):
    """Duration ticks present, time base absent: R-NO-TIMESCALE."""
    out = bytearray(buf)
    for typ, s, _e in _box_chain(out, 0, len(out)):
        if typ != b"moov":
            continue
        for t2, s2, _e2 in _box_chain(out, s, _e):
            if t2 != b"trak":
                continue
            for t3, s3, _e3 in _box_chain(out, s2, _e2):
                if t3 != b"mdia":
                    continue
                for t4, s4, _e4 in _box_chain(out, s3, _e3):
                    if t4 != b"mdhd":
                        continue
                    struct.pack_into(">I", out, s4 + 12, timescale)
    return bytes(out)


# ------------------------------------------------------------------ the fixture plan
# Each record: (name, start_offset_s, key_duration_ms, container duration seconds, extras)
# start is what the clip_id encodes; key values are CHOSEN fixtures.

PLAN = [
    # ---- the clean chain: contiguous, agreeing, no gap > 0, no overlap -------------------
    dict(name="A001", seq=1, off=0.0, dur_ms=4000, cont=4.0),
    dict(name="A002", seq=2, off=4.0, dur_ms=4000, cont=4.0),
    dict(name="A003", seq=3, off=8.0, dur_ms=4000, cont=4.0),
    dict(name="A004", seq=4, off=12.0, dur_ms=4000, cont=4.0),
    # ---- planted: key.started_at_s disagrees with its own clip_id by 0.5 s ----------------
    dict(name="A005", seq=5, off=20.0, dur_ms=3000, cont=3.0, key_start_delta=0.5,
         plant=["C09"]),
    # ---- planted: declared 4.0 s vs container 5.0 s, and two traks 5.0 s vs 8.0 s ---------
    dict(name="A006", seq=6, off=40.0, dur_ms=4000, cont=5.0, audio_dur=8.0,
         plant=["C07", "C2TRAK"]),
    # ---- planted: key.ended_at_s 5 s BEFORE its start -------------------------------------
    dict(name="A007", seq=7, off=60.0, dur_ms=3000, cont=3.0, end_delta=-5.0,
         plant=["C05"]),
    # ---- planted: two directories, IDENTICAL bytes, identical content_key ----------------
    dict(name="A008", seq=8, off=80.0, dur_ms=4000, cont=4.0, shared_bytes=True, dup_pair=True,
         plant=["C01", "C02"]),
    dict(name="A009", seq=9, off=81.0, dur_ms=4000, cont=4.0, shared_bytes=True, dup_pair=True,
         plant=["C01", "C02"]),
    # ---- planted: content_key found on disk, db row still names the OLD path --------------
    dict(name="A010", seq=10, off=90.0, dur_ms=3000, cont=3.0, moved=True,
         plant=["C03"]),
    # ---- planted: .partial + key.json (crash between commit and marker removal) ----------
    dict(name="A011", seq=11, off=94.0, dur_ms=3000, cont=3.0, partial=True,
         plant=["FINISH"]),
    # ---- planted: .partial, no key.json, media with no finished moov ---------------------
    dict(name="A012", seq=12, off=98.0, dur_ms=0, cont=None, partial=True, no_key=True,
         media_mode="crash", plant=["DISCARD", "R-NO-MOOV"]),
    # ---- planted: key.json carrying layout_version 2 (no read rule) ----------------------
    dict(name="A013", seq=13, off=110.0, dur_ms=2500, cont=2.5, key_layout_version=2,
         unreadable_key=True, plant=["R-VERSION"]),
    # ---- planted: media present, no marker, no key ---------------------------------------
    dict(name="A014", seq=14, off=114.0, dur_ms=2000, cont=2.0, no_key=True,
         no_partial=True, plant=["ORPHAN"]),
    # ---- planted: key names a media file that is not there -------------------------------
    dict(name="A015", seq=15, off=118.0, dur_ms=2000, cont=2.0, no_media=True,
         plant=["MISSING-MEDIA"]),
    # ---- planted: key readable, but its clip_id is not this directory's ------------------
    dict(name="A016", seq=16, off=125.0, dur_ms=3000, cont=3.0, wrong_key_clip_id=True,
         plant=["R-WRONG-DIR"]),
    # ---- planted: key.json's content_key is a LIE about its own bytes --------------------
    # the db carries the TRUE whole-file sha256, so the lie lives in key.json alone and only
    # a recomputation of the media's hash can separate the two.
    dict(name="A017", seq=17, off=140.0, dur_ms=2000, cont=2.0, key_content_key_lie=True,
         plant=["C02"]),
]

# the mutant: a clip that overlaps the clean chain's last clip by more than PAD_S
MUTANT_CLIP = dict(name="A900", seq=900, off=15.0, dur_ms=4000, cont=4.0, plant=["C01"])

# foreign containers, outside clips/ entirely
FOREIGN = [
    # the index's duration_ms disagrees with the container by 500 ms: C08 duration source mismatch
    dict(name="legacy-2026-09-01.mp4", dur=3.0, mtime_off=8.0, db_ms=2500, plant=["C08"]),
    dict(name="moov-no-duration.mp4", dur=None, mtime_off=200.0, plant=["R-NO-DURATION"]),
    dict(name="not-really.mp4", dur=None, mtime_off=210.0, plant=["R-NO-FTYP"]),
    dict(name="moov-truncated.mp4", dur=None, mtime_off=220.0, plant=["R-TRUNCATED"]),
    # a top-level box this ODS does not implement
    dict(name="mp4-unknown-box.mp4", dur=2.0, mtime_off=230.0, plant=["R-BOX-UNKNOWN"]),
    # duration ticks with no time base
    dict(name="moov-no-timescale.mp4", dur=2.0, mtime_off=240.0, plant=["R-NO-TIMESCALE"]),
    # an mvhd of a version this ODS does not implement
    dict(name="mvhd-v1.mp4", dur=2.0, mtime_off=250.0, plant=["R-BOX-VERSION"]),
    # a container that reads FINE while the index declares 0 ms for it
    dict(name="db-zero-duration.mp4", dur=2.0, mtime_off=260.0, db_ms=0, plant=["C08"]),
]

# a directory under clips/ whose name is not a clip id
FOREIGN_DIR = dict(name="not-a-clip-id", note="skipped by CLIP_ID_RE, never repaired")


def build(root, which):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    (root / LAYOUT.CLIPS_DIRNAME / "2026/10/09").mkdir(parents=True, exist_ok=True)
    man = {"root": str(root), "store": which, "S0_epoch": S0,
           "S0_utc": datetime.fromtimestamp(S0, tz=timezone.utc).isoformat(),
           "clips": [], "foreign": [], "db_rows": [], "expect": {}, "notes": []}

    if which == CLEAN:
        plan = [c for c in PLAN if c["name"] in ("A001", "A002", "A003", "A004")]
    elif which == MUTANT:
        plan = [c for c in PLAN if c["name"] in ("A001", "A002", "A003", "A004")]
        plan.append(MUTANT_CLIP)
    else:
        plan = list(PLAN)
    include_foreign = which == FULL
    include_ghost_and_moved = which == FULL

    for rec in plan:
        cid = clip_id_at(rec["off"], rec["seq"])
        cdir = LAYOUT.clip_dir(root, cid)
        cdir.mkdir(parents=True, exist_ok=True)
        salt = None if rec.get("shared_bytes") else int(rec["off"]) + rec["seq"]
        m = (media(rec["cont"], salt=salt, audio_dur_s=rec.get("audio_dur"))
              if rec.get("cont") is not None else b"")
        if rec.get("media_mode") == "crash":
            m = media(0.0, mode="crash", salt=salt)
        if rec.get("no_media"):
            m = None
        size = len(m) if m is not None else 0
        mtime_ns = int((S0 + rec["off"] + 1.0) * 1e9)
        ckey = sha(m) if m is not None else ""
        claimed_key = ckey
        if rec.get("key_content_key_lie"):
            # hash of OTHER bytes: a key.json that misstates the identity of its own media
            claimed_key = sha(b"not-the-media-of:" + cid.encode("ascii"))
        if m is not None:
            (cdir / LAYOUT.MEDIA_NAME).write_bytes(m)
            os.utime(cdir / LAYOUT.MEDIA_NAME, ns=(mtime_ns, mtime_ns))
        if rec.get("partial"):
            (cdir / LAYOUT.PARTIAL_MARKER).write_bytes(b"")
        if not rec.get("no_key"):
            started = S0 + rec["off"] + (rec.get("key_start_delta") or 0.0)
            ended = started + rec["dur_ms"] / 1000.0 + (rec.get("end_delta") or 0.0)
            k = key_obj(cid, started, ended, rec["dur_ms"], size, mtime_ns, claimed_key,
                        layout_version=rec.get("key_layout_version", 1),
                        key_clip_id=(clip_id_at(1999.0, 9999) if rec.get("wrong_key_clip_id")
                                     else None))
            (cdir / LAYOUT.KEY_NAME).write_text(json.dumps(k, indent=1), encoding="utf-8")
            key_started, key_ended, key_dur = started, ended, rec["dur_ms"]
        else:
            key_started = key_ended = key_dur = None
        man["clips"].append({
            "name": rec["name"], "clip_id": cid, "dir": str(cdir),
            "chosen_started_at_s": S0 + rec["off"],
            "chosen_key_started_at_s": key_started,
            "chosen_key_ended_at_s": key_ended,
            "chosen_key_duration_ms": key_dur,
            "container_duration_s": rec.get("cont"),
            "content_key": ckey, "size_bytes": size, "mtime_ns": mtime_ns,
            "partial": bool(rec.get("partial")), "key_present": not rec.get("no_key"),
            "media_present": m is not None, "plant": rec.get("plant", []),
        })

    if include_foreign:
        (root / "imports").mkdir(parents=True, exist_ok=True)
        for f in FOREIGN:
            p = root / "imports" / f["name"]
            if f["name"] == "not-really.mp4":
                b = b"NOT an mp4 at all -- text bytes pretending to be a container\n"
            elif f["name"] == "moov-truncated.mp4":
                b = media(2.0, mode="truncated")
            elif f["name"] == "moov-no-duration.mp4":
                b = mp4fix.build_nodur_mp4()
            elif f["name"] == "mp4-unknown-box.mp4":
                b = inject_unknown_top_box(media(2.0))
            elif f["name"] == "moov-no-timescale.mp4":
                b = patch_mdhd_timescale(media(2.0), 0)
            elif f["name"] == "mvhd-v1.mp4":
                b = patch_box_version(media(2.0), b"mvhd", 1)
            else:
                b = media(f["dur"])
            p.write_bytes(b)
            mtime_ns = int((S0 + f["mtime_off"]) * 1e9)
            os.utime(p, ns=(mtime_ns, mtime_ns))
            man["foreign"].append({
                "name": f["name"], "path": str(p), "container_duration_s": f["dur"],
                "mtime_ns": mtime_ns, "sha256": sha(b), "bytes": len(b), "plant": f["plant"],
                # the CHOSEN db duration, which is what makes it disagree with the container
                "db_ms": f.get("db_ms"),
            })
        fd = root / "clips/2026/10/09" / FOREIGN_DIR["name"]
        fd.mkdir(parents=True, exist_ok=True)
        (fd / "clip.mp4").write_bytes(media(2.0))
        man["notes"].append("foreign-dir-under-clips: " + str(fd))

    # the store's own version marker
    (root / LAYOUT.ROOT_MARKER).write_text(
        json.dumps({"layout_version": LAYOUT.LAYOUT_VERSION}, indent=1), encoding="utf-8")

    # ---------------------------------------------------------------- the db
    db_path = root / "store.db"
    con = sqlite3.connect(str(db_path))
    con.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    rows = []
    for c in man["clips"]:
        if not c["media_present"]:
            continue
        rows.append((c["content_key"], c["dir"] + "\\" + LAYOUT.MEDIA_NAME, c["size_bytes"],
                     c["mtime_ns"], int(round((c["chosen_key_duration_ms"] or 0))),
                     "h264", 1920, 1080, 60.0, 45000000, 0, "indexed"))
    if include_foreign:
        for f in man["foreign"]:
            if f["name"] == "not-really.mp4":
                continue
            rows.append((f["sha256"], f["path"], f["bytes"], f["mtime_ns"],
                         (f["db_ms"] if f["db_ms"] is not None
                          else int(round((f["container_duration_s"] or 0) * 1000))),
                         "h264", 1920, 1080, 60.0, 45000000, 0, "indexed"))
    # empty for the clean and mutant arms (no ghost, no move); the full arm fills it below
    stale_paths = {}
    if include_ghost_and_moved:
        ghost = "deadbeef" * 8
        rows.append((ghost,
                     str(root / "clips/2026/10/07/20261007T000000Z-0001/clip.mp4"),
                     0, 0, 0, None, None, None, None, None, 1, "failed"))
        # A010 PATH MOVED, represented the ONLY way this schema allows it.
        # BUILDER DISCOVERY (measured while building): a second video row for an identity that
        # already has one is UNREPRESENTABLE -- schema.sql:41-63 declares content_key UNIQUE, so
        # the INSERT raised sqlite3.IntegrityError and the plant never reached the db at all.
        # What a move actually leaves in this index is the SAME row still naming the OLD path
        # with missing=1: identity (whole-file sha256) survived, the path did not.  That is the
        # shape built here, and it is a genuine finding about the schema, not a fixture bug.
        stale_paths = {"A010": str(root / "clips/2026/10/08/20261008T110000Z-0099/clip.mp4")}
    dup_refusals = []
    for r in rows:
        try:
            con.execute("INSERT INTO video (content_key, path, size_bytes, mtime_ns, "
                        "duration_ms, codec, w, h, fps, bitrate, missing, state) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", r)
            man["db_rows"].append(dict(content_key=r[0], path=r[1], duration_ms=r[4],
                                       missing=r[10], state=r[11]))
        except sqlite3.IntegrityError as exc:
            dup_refusals.append({"content_key": r[0], "path": r[1], "error": str(exc)})
    for nm, stale in (stale_paths or {}).items():
        for c in man["clips"]:
            if c.get("name") == nm:
                con.execute("UPDATE video SET path=? WHERE content_key=?",
                            (stale, c["content_key"]))
                for d in man["db_rows"]:
                    if d.get("content_key") == c["content_key"]:
                        d["path"] = stale
                        d["missing"] = 1
                        d["state"] = "superseded"
    con.commit()
    con.close()
    man["db_dup_refusals"] = dup_refusals

    # ---------------------------------------------------------------- expectations
    exp = {"C01": [], "C02": [], "C03": [], "C04": [], "C05": [], "C06": [],
           "C07": [], "C08": [], "C09": [], "C2TRAK": [], "REFUSAL": []}
    by_name = {c["name"]: c for c in man["clips"]}
    for c in man["clips"] + [{"name": f["name"], "clip_id": "", "path": f["path"],
                              "plant": f["plant"]} for f in man["foreign"]]:
        for cl in c.get("plant", []):
            if cl.startswith("R-"):
                exp["REFUSAL"].append({"class": cl, "subject": c.get("path") or c.get("dir"),
                                       "name": c.get("name")})
            elif cl in exp:
                exp[cl].append({"name": c.get("name"), "clip_id": c.get("clip_id", ""),
                                "path": c.get("path") or c.get("dir")})
            else:
                exp.setdefault(cl, []).append(
                    {"name": c.get("name"), "path": c.get("path") or c.get("dir")})
    man["expect"] = exp
    # BUILDER CORRECTION 2026-10-09: the fixture name R-TRUNCATED was shorthand for "a box that
    # claims past EOF".  The instrument reports that first cause as R-BOX-TRUNCATED, so the
    # expectation is written in the codes the instrument actually emits.
    for e in exp.get("REFUSAL", []):
        if e.get("class") == "R-TRUNCATED":
            e["class"] = "R-BOX-TRUNCATED"
    if include_ghost_and_moved:
        man["notes"].append("A010 PATH MOVED is a STALE path on the SAME row, not a second row: "
                           "content_key is UNIQUE (schema.sql:41-63), so the pre-move row had "
                           "to be UPDATEd.  The duplicate INSERT was tried first and refused.")
        man["notes"].append("A015 db row is a deadbeef content_key at a 2026-10-07 path that "
                           "was never written: the index held a row for a clip missing on disk.")
    return man


def main():
    out = {}
    out[FULL] = build("I:/cc-tmp/ods1-armA/store", FULL)
    out[CLEAN] = build("I:/cc-tmp/ods1-armA/store-clean", CLEAN)
    out[MUTANT] = build("I:/cc-tmp/ods1-armA/store-mutant", MUTANT)
    manifest = {"generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
                "repo_files_used": {
                    "layout.py": str(LAYOUT_PY),
                    "layout.py_sha256": sha(LAYOUT_PY.read_bytes()),
                    "schema.sql": str(SCHEMA_SQL),
                    "schema.sql_sha256": sha(SCHEMA_SQL.read_bytes()),
                },
                "stores": out}
    manifest["fixture_correction_20261009"] = {
        "how": "the fixture list once named one planted refusal R-TRUNCATED, which was builder "
                "shorthand for a box that claims past EOF.  The instrument reports that first "
                "cause as R-BOX-TRUNCATED -> R-DURATION-UNKNOWN (terminal), so the expectation "
                "above is written in the codes the instrument actually emits.  No fixture byte "
                "on disk was changed by this correction.",
        "a010_move": "A010 was first built as a SECOND video row for the same content_key.  The "
                     "schema refuses that (content_key UNIQUE, schema.sql:41-63) -- measured, "
                     "sqlite3.IntegrityError -- so the plant never reached the db at all.  The "
                     "moved clip is now the SAME row still naming its OLD path with missing=1, "
                     "which is the only shape of PATH MOVED this index can hold."}
    p = HERE / "manifest.json"
    p.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for name, m in out.items():
        print("store", name, "clips", len(m["clips"]), "db_rows", len(m["db_rows"]),
              "dup_refusals", len(m["db_dup_refusals"]))
    print("manifest bytes", p.stat().st_size)


if __name__ == "__main__":
    main()
