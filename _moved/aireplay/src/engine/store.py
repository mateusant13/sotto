"""src/engine/store.py -- the Engine's durable spine (SQLite, committed-before-ack).

The law this module exists to hold: a clip row is COMMITTED before the Engine tells
anyone the clip exists, and the row survives the Engine being killed outright
(TerminateProcess -- ARM-F).  synchronous=FULL + WAL is what buys that; NORMAL (the
index's choice) does not.

content_key is the whole-file SHA-256 hex, computed at commit time FROM THE FILE, so
it can be recomputed by anyone later and is unique per file.  That is the anchor the
Engine shares with lane B's index (src/index/schema.sql, video.content_key).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_SQL = os.path.join(HERE, "schema.sql")

CHUNK = 1 << 20


def content_key_of(path):
    """Whole-file SHA-256 hex (64 chars).  The file must be closed and stable."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class Spine(object):
    def __init__(self, path):
        self.path = path
        self.con = sqlite3.connect(path, timeout=10.0, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        with open(SCHEMA_SQL, "r", encoding="utf-8") as f:
            ddl = f.read()
        self.con.executescript(ddl)
        self.con.execute("INSERT OR REPLACE INTO engine_meta(k,v) VALUES('opened_at',?)",
                         ("%.3f" % time.time(),))

    # ---- the two-step clip lifecycle -------------------------------------------------
    def anchor(self, clip_id, path, started_at, modes="", frames=0):
        """ROW BEFORE BYTES: the row exists while the file is still being written.

        Mirrors the capture child's 'cutting' anchor (src/capture/replay.cpp
        fire_anchor): a crash can orphan a ROW (findable, repairable) and never a FILE.
        """
        self.con.execute(
            "INSERT OR REPLACE INTO clip(clip_id,path,started_at,modes,frames,state,"
            "created_at) VALUES(?,?,?,?,?,'cutting',?)",
            (clip_id, path, float(started_at), modes, int(frames), time.time()))

    def commit_clip(self, clip_id, size_bytes=None, frames=None, duration_ms=None, path=None):
        """Compute content_key FROM THE FILE and COMMIT the row.  fsync'd (FULL).

        Returns the row.  Raises if the file is missing -- an engine that acked a clip
        whose bytes are not on disk would be lying, so it does not.
        """
        row = self.con.execute("SELECT * FROM clip WHERE clip_id=?", (clip_id,)).fetchone()
        if row is None:
            raise KeyError("clip %r is not anchored" % (clip_id,))
        if path is not None and path != row["path"]:
            # the child names the file authoritatively; the anchor carried the
            # engine's PREDICTION.  Correct the row before the key is computed.
            self.con.execute("UPDATE clip SET path=? WHERE clip_id=?", (path, clip_id))
        path = path or row["path"]
        if not os.path.exists(path):
            raise FileNotFoundError("clip %r has no file on disk: %s" % (clip_id, path))
        key = content_key_of(path)
        size = os.path.getsize(path) if size_bytes is None else int(size_bytes)
        self.con.execute(
            "UPDATE clip SET content_key=?, size_bytes=?, frames=COALESCE(?,frames), "
            "duration_ms=COALESCE(?,duration_ms), state='done', committed_at=? "
            "WHERE clip_id=?",
            (key, size, frames, duration_ms, time.time(), clip_id))
        return self.get(clip_id)

    def mark_failed(self, clip_id, reason="failed"):
        self.con.execute("UPDATE clip SET state=?, asr_state='dead' WHERE clip_id=?",
                         (reason, clip_id))

    def set_asr_state(self, clip_id, state):
        self.con.execute("UPDATE clip SET asr_state=? WHERE clip_id=?", (state, clip_id))

    # ---- children of the clip -------------------------------------------------------
    def add_speech(self, clip_id, segs):
        now = time.time()
        rows = []
        for i, s in enumerate(segs):
            rows.append((clip_id, i, float(s.get("t0", 0.0)), float(s.get("t1", 0.0)),
                         str(s.get("text", "")), str(s.get("provider", "asr.transcribe")),
                         s.get("infer_s"), now))
            self.con.execute(
                "INSERT OR REPLACE INTO clip_text(clip_id,source,text) VALUES(?,?,?)",
                (clip_id, "speech", str(s.get("text", ""))))
        self.con.executemany(
            "INSERT OR REPLACE INTO speech_segment(clip_id,seg_index,t0,t1,text,provider,"
            "infer_s,created_at) VALUES(?,?,?,?,?,?,?,?)", rows)
        return len(rows)

    def add_ocr(self, clip_id, rows):
        now = time.time()
        self.con.executemany(
            "INSERT INTO ocr(clip_id,t_ms,text,box,created_at) VALUES(?,?,?,?,?)",
            [(clip_id, int(r["t_ms"]), str(r["text"]), r.get("box"), now) for r in rows])
        for r in rows:
            self.con.execute("INSERT INTO clip_text(clip_id,source,text) VALUES(?,?,?)",
                             (clip_id, "ocr", str(r["text"])))

    def add_visual(self, clip_id, rows):
        now = time.time()
        self.con.executemany(
            "INSERT INTO visual(clip_id,t_ms,label,score,created_at) VALUES(?,?,?,?,?)",
            [(clip_id, int(r["t_ms"]), str(r["label"]), float(r["score"]), now) for r in rows])

    # ---- reads ----------------------------------------------------------------------
    def get(self, clip_id):
        return self.con.execute("SELECT * FROM clip WHERE clip_id=?", (clip_id,)).fetchone()

    def clips(self, state=None):
        if state is None:
            return self.con.execute("SELECT * FROM clip ORDER BY started_at").fetchall()
        return self.con.execute("SELECT * FROM clip WHERE state=? ORDER BY started_at",
                                (state,)).fetchall()

    def counts(self):
        out = {}
        for k in ("clip", "speech_segment", "ocr", "visual", "clip_text"):
            out[k] = self.con.execute("SELECT COUNT(*) FROM %s" % k).fetchone()[0]
        out["clip_done"] = self.con.execute(
            "SELECT COUNT(*) FROM clip WHERE state='done'").fetchone()[0]
        out["clip_cutting"] = self.con.execute(
            "SELECT COUNT(*) FROM clip WHERE state='cutting'").fetchone()[0]
        return out

    def search(self, text, limit=50):
        """Provenance-carrying search: every hit names its clip and content_key."""
        like = "%" + text.replace("%", "").replace("_", "") + "%"
        rows = self.con.execute(
            "SELECT c.clip_id AS clip_id, c.content_key AS content_key, c.path AS path, "
            "       ct.source AS source, ct.text AS text "
            "FROM clip_text ct JOIN clip c ON c.clip_id=ct.clip_id "
            "WHERE ct.text LIKE ? LIMIT ?", (like, int(limit))).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        try:
            self.con.execute("PRAGMA optimize")
        except Exception:
            pass
        self.con.close()
