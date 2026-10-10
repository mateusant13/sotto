"""CHECK ARM A -- an INDEPENDENT second reader.

ods1.py checks its own expectations (the instrument grading its own homework).  This file does
NOT share a line of code with it: it reads manifest.json, walks the three stores on disk, reads
the three JSON twins, and answers four questions on its own:

  Q1 do the stores hold exactly what the manifest says they hold (clips / foreign / db rows)?
  Q2 does every expectation block in the manifest have a matching finding in the run twin?
  Q3 does every planted contradiction actually PRODUCE a finding (a miss is the finding)?
  Q4 do the two control arms still hold the shape they are controls FOR
     (clean = silence, mutant = exactly one red, that one being C01)?

Exit 0 only when all four hold.  Pure stdlib.  ASCII only.
"""
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "manifest.json")
LAYOUT_PY = os.path.join(HERE, "..", "..", "..", "sotto", "_moved", "aireplay",
                        "src", "storage", "layout.py")
FAILS = []
CHECKS = [0]


def ck(name, ok, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILS.append("%s :: %s" % (name, detail))
        print("RED   %s :: %s" % (name, detail))
    else:
        print("green %s :: %s" % (name, detail))


def main():
    man = json.load(open(MANIFEST, "r", encoding="utf-8"))
    twins = {}
    for store in ("clean", "mutant", "full"):
        s = man["stores"][store]
        root = s["root"]
        twin = os.path.join(HERE, "out-%s.json" % store)
        ck("store root exists (%s)" % store, os.path.isdir(root), root)
        ck("run twin exists (%s)" % store, os.path.isfile(twin), twin)
        twins[store] = json.load(open(twin, "r", encoding="utf-8")) if os.path.isfile(twin) else {}
        q1(root, s, store, twins)
    expectation_audit(man, twins)
    q3(man, twins)
    q3b(man, twins)
    q4(man, twins)


def clip_dir_pat():
    """The clip dir name SHAPE, re-stated by reading, never by importing the subject.
    H:/sotto/_moved/aireplay/src/storage/layout.py:71-73 builds the dir from a UTC triple and
    :108-121 parses it back.  This checker re-states the shape so that a change in the shape
    itself shows up here as a census mismatch, not as a silent agreement.
    """
    import re
    return re.compile(r"^\d{8}T\d{6}Z-\d{4}$")


def sha256_of(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        chunk = fh.read(65536)
        while chunk:
            h.update(chunk)
            chunk = fh.read(65536)
    return h.hexdigest()


def census(root):
    """Walk the store WITHOUT the instrument: count clips, foreign files, db rows, dups."""
    pat = clip_dir_pat()
    clips, foreign = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for d in dirnames:
            if pat.match(d):
                clips.append(os.path.join(dirpath, d))
            else:
                keep.append(d)
        dirnames[:] = keep
        for fn in sorted(filenames):
            if dirpath == root and (fn == "layout.json" or fn.startswith("store.db")):
                continue
            foreign.append(os.path.join(dirpath, fn))
    rows, dups = 0, 0
    db = os.path.join(root, "store.db")
    if os.path.exists(db):
        cx = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        seen = {}
        for ck_, _p in cx.execute("SELECT content_key, path FROM video").fetchall():
            rows += 1
            seen[ck_] = seen.get(ck_, 0) + 1
        dups = sum(1 for v in seen.values() if v > 1)
        cx.close()
    return {"clips": clips, "foreign": foreign, "db_rows": rows, "db_dups": dups}


# ---- a MINIMAL, INDEPENDENT mp4 reader: only what a duration claim needs ----------------
# Boxes are size:u32 + type:4chars, then payload.  This walks them, finds moov, finds the
# trak whose hdlr says vide, and sums stts.  It is written here from the container format,
# NOT borrowed from the instrument under test -- if the two disagree the disagreement is the
# finding, which is the whole point of a second reader.

def rd_u32(b, o):
    return int.from_bytes(b[o:o + 4], "big")


def rd_u64(b, o):
    return int.from_bytes(b[o:o + 8], "big")


def boxes(b, start, end):
    out, o = [], start
    while o + 8 <= end:
        size = rd_u32(b, o)
        typ = b[o + 4:o + 8].decode("latin-1")
        hdr = 8
        if size == 1:
            if o + 16 > end:
                break
            size = rd_u64(b, o + 8)
            hdr = 16
        elif size == 0:
            size = end - o
        if size < hdr or o + size > end:
            break
        out.append((typ, o + hdr, o + size))
        o += size
    return out


def trak_kind(b, s, e):
    for t, bs, be in boxes(b, s, e):
        if t == "hdlr" and be - bs >= 12:
            return b[bs + 8:bs + 12].decode("latin-1")
    return "?"


def stts_ms(b, s, e, timescale):
    total = 0
    for t, bs, be in boxes(b, s, e):
        if t != "stts":
            continue
        n = rd_u32(b, bs + 4)
        o = bs + 8
        for _ in range(n):
            if o + 8 > be:
                break
            cnt = rd_u32(b, o)
            delta = rd_u32(b, o + 4)
            total += cnt * delta
            o += 8
    if timescale:
        return total * 1000 // timescale
    return None


def mdhd_timescale(b, s, e):
    for t, bs, be in boxes(b, s, e):
        if t == "mdhd":
            ver = b[bs]
            if ver == 1 and bs + 4 + 8 + 8 + 4 <= be:
                return rd_u32(b, bs + 4 + 8 + 8)
            if ver == 0 and bs + 4 + 4 + 4 + 4 <= be:
                return rd_u32(b, bs + 4 + 4 + 4)
    return None


def video_trak_ms(b):
    """Duration of the VIDEO trak in ms, or None when it cannot be derived."""
    for t, s, e in boxes(b, 0, len(b)):
        if t != "moov":
            continue
        for tt, ts, te in boxes(b, s, e):
            if tt != "trak":
                continue
            if trak_kind(b, ts, te) != "vide":
                continue
            for mt, ms, me in boxes(b, ts, te):
                if mt != "mdia":
                    continue
                ts_ = mdhd_timescale(b, ms, me)
                for st, ss, se in boxes(b, ms, me):
                    if st == "minf":
                        for m2, s2, e2 in boxes(b, ss, se):
                            if m2 == "stbl":
                                return stts_ms(b, s2, e2, ts_)
    return None


# ---- Q2: every manifest expectation must have a matching twin finding -------------
VERDICT_FOR = {"FINISH": "partial-committed",
               "DISCARD": "partial-uncommitted",
               "ORPHAN": "orphan-key",
               "MISSING-MEDIA": "missing-media"}


def row_path(r):
    return r.get("dir") or r.get("path") or ""


def norm(p):
    return str(p or "").replace("/", "\\")


def under(entry_path, ev):
    """True when the evidence path IS the expected file or lives inside it."""
    ev, p = norm(ev), norm(entry_path)
    if not ev or not p:
        return False
    return ev == p or ev.startswith(p + "\\")


def expectation_audit(man, twins):
    checked = 0
    for sname in ("clean", "mutant", "full"):
        exp = (man["stores"][sname].get("expect") or {})
        twin = twins[sname]
        rows = twin.get("rows") or []
        findings = twin.get("findings") or []
        for cls in sorted(exp):
            for entry in (exp[cls] or []):
                checked += 1
                ep = entry.get("path") or entry.get("subject") or ""
                name = entry.get("name") or "?"
                if cls in VERDICT_FOR:
                    want = VERDICT_FOR[cls]
                    hit = [r for r in rows
                           if row_path(r) == norm(ep) and r.get("verdict") == want]
                    want_txt = "row verdict " + want
                elif cls == "REFUSAL":
                    want_txt = "REFUSAL code " + (entry.get("class") or "?")
                    hit = []
                    for f in findings:
                        if f.get("cls") != "REFUSAL":
                            continue
                        v = f.get("values") or {}
                        if entry.get("class") not in (v.get("code"), v.get("terminal")):
                            continue
                        if any(under(ep, x) for x in f.get("evidence_paths") or []):
                            hit.append(f)
                else:
                    want_txt = "finding class " + cls
                    hit = [f for f in findings if f.get("cls") == cls
                           and any(under(ep, x) for x in f.get("evidence_paths") or [])]
                ck("[%s] %s -> %s at %s" % (sname, name, want_txt, ep),
                   len(hit) > 0, "no twin row carries it" if not hit else "%d match(es)" % len(hit))
    return checked


# ---- Q3: re-derive every planted contradiction from the bytes ---------------------
def clip_id_epoch(cid):
    import calendar, re
    m = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z-\d{4}$", cid)
    if not m:
        return None
    y, mo, d, h, mi, s = [int(m.group(i)) for i in range(1, 7)]
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))


def cdir(root, cid):
    return os.path.join(root, "clips", cid[0:4], cid[4:6], cid[6:8], cid)


def key_at(root, cid):
    p = os.path.join(cdir(root, cid), "key.json")
    if not os.path.isfile(p):
        return None
    fh = open(p, "rb")
    try:
        return json.loads(fh.read().decode("utf-8"))
    finally:
        fh.close()


def db_rows_of(root):
    out = {}
    p = os.path.join(root, "store.db")
    if not os.path.exists(p):
        return out
    cx = sqlite3.connect("file:%s?mode=ro" % norm(p), uri=True)
    for k, d, path in cx.execute(
            "SELECT content_key, duration_ms, path FROM video").fetchall():
        out.setdefault(k, []).append({"duration_ms": d, "path": path})
    cx.close()
    return out


def hdlrs(b, s, e):
    """Raw byte scan for hdlr inside [s,e): the type is 4 bytes after version+flags."""
    out = []
    i = b.find(b"hdlr", s, e)
    while i != -1 and i + 12 <= e:
        out.append(b[i + 12:i + 16].decode("latin-1"))
        i = b.find(b"hdlr", i + 4, e)
    return out


def mdhd_ts(b, s, e):
    """Timescale from an mdhd CONTENT window: version(1)+flags(3)+creation(4)+modification(4)."""
    if e - s < 20:
        return None
    return rd_u32(b, s + 12)


def trak_facts(b):
    """[(handler, ms)] per trak, in file order, from the boxes themselves."""
    out = []
    for mt, ms_, me in boxes(b, 0, len(b)):
        if mt != "moov":
            continue
        for tt, ts, te in boxes(b, ms_, me):
            if tt != "trak":
                continue
            kind, tscale, dur = "?", None, None
            for d1, s1, e1 in boxes(b, ts, te):
                if d1 != "mdia":
                    continue
                hs = hdlrs(b, s1, e1)
                if hs:
                    kind = hs[0]
                for d2, s2, e2 in boxes(b, s1, e1):
                    if d2 == "mdhd":
                        tscale = mdhd_ts(b, s2, e2)
                    if d2 == "minf":
                        for d3, s3, e3 in boxes(b, s2, e2):
                            if d3 == "stbl":
                                dur = stts_ms(b, s3, e3, tscale)
            out.append((kind, dur))
    return out


def video_ms_of(path):
    fh = open(path, "rb")
    try:
        b = fh.read()
    finally:
        fh.close()
    tf = trak_facts(b)
    for kind, ms in tf:
        if kind == "vide" and ms is not None:
            return ms
    for kind, ms in tf:
        if ms is not None:
            return ms
    return None


# ---- Q1: what is on disk vs what the manifest says ------------------------------
def q1(root, s, store, twins=None):
    got = census(root)
    ck("[%s] clip dirs on disk == manifest" % store,
       len(got["clips"]) == len(s.get("clips") or []),
       "disk=%d manifest=%d" % (len(got["clips"]), len(s.get("clips") or [])))
    df = len(got["foreign"])
    tf = len([r for r in (twins.get(store, {}).get("rows") or []) if r.get("kind") == "foreign"])
    ck("[%s] disk foreign files == the instrument foreign rows" % store,
       df == tf and df >= 0, "disk=%d rows=%d" % (df, tf))
    ck("[%s] each manifest foreign file exists on disk" % store,
       all(os.path.isfile(fo["path"] if isinstance(fo, dict) else fo) for fo in (s.get("foreign") or [])),
       "manifest foreign=%d" % len(s.get("foreign") or []))
    ck("[%s] db rows == manifest" % store,
       got["db_rows"] == len(s.get("db_rows") or []),
       "disk=%d manifest=%d" % (got["db_rows"], len(s.get("db_rows") or [])))
    ck("[%s] no duplicate content_key in the index (schema.sql:44 UNIQUE)" % store,
       got["db_dups"] == 0, "dups=" + str(got["db_dups"]))


# ---- Q3: does each planted contradiction PRODUCE a finding? ----------------------
def q3(man, twins):
    root = man["stores"]["full"]["root"]
    findings = twins["full"].get("findings") or []
    rows = twins["full"].get("rows") or []

    def has(cls, frag, want=None):
        for f in findings:
            if f.get("cls") != cls:
                continue
            blob = str(f.get("subject")) + " " + " ".join(str(p) for p in (f.get("evidence_paths") or []))
            if frag not in blob:
                continue
            if want is None:
                return f
            v = f.get("values") or {}
            if all(v.get(k) == val for k, val in want.items()):
                return f
        return None

    def facts(cid):
        key = key_at(root, cid) or {}
        media = os.path.join(cdir(root, cid), "clip.mp4")
        db = db_rows_of(root).get(key.get("content_key") or "-", [])
        return {"key": key, "media": media,
                "db_ms": (db[0]["duration_ms"] if db else None),
                "db_path": (db[0]["path"] if db else None),
                "ms": video_ms_of(media) if os.path.isfile(media) else None,
                "traks": trak_facts(open(media, "rb").read()) if os.path.isfile(media) else []}

    # C01/C02 -- two clip dirs, one identity, and an overlap wider than PAD_S
    a = "20261009T120120Z-0008"
    b = "20261009T120121Z-0009"
    fa, fb = facts(a), facts(b)
    ck("A008 and A009 are byte-identical (one identity, two dirs)",
       sha256_of(fa["media"]) == sha256_of(fb["media"]),
       "sha256 " + sha256_of(fa["media"])[:16])
    ov = min(fa["key"]["ended_at_s"], fb["key"]["ended_at_s"]) - max(fa["key"]["started_at_s"], fb["key"]["started_at_s"])
    ck("A008/A009 overlap by more than PAD_S = 0.10 s (specs/02-asr.md:165)",
       ov > 0.10, "overlap=%.3f s" % ov)
    ck("twin fires C01 on that pair",
       has("C01", a) is not None and has("C01", b) is not None, "subject-subject pair")
    cf = has("C02", a)
    ck("twin C02 on A008/A009 names the index UNIQUE(content_key) limit (schema.sql:44)",
       cf is not None and "UNIQUE" in str(cf.get("detail") or ""), str(cf.get("detail") if cf else None))
    ck("twin C02 on the identical pair carries both member paths",
       cf is not None and len((cf.get("evidence_paths") or [])) == 2,
       "evidence=" + str((cf or {}).get("evidence_paths")))

    # C02 -- a key.json whose content_key is NOT what the bytes hash to
    a17 = facts("20261009T120220Z-0017")
    real = sha256_of(a17["media"])
    ck("A017 key.content_key is a lie about its own bytes",
       a17["key"].get("content_key") != real, "claimed=" + (a17["key"].get("content_key") or "?")[:16] + " real=" + real[:16])
    ck("twin fires C02 IDENTITY CLAIM LIES on A017", has("C02", "20261009T120220Z-0017") is not None, "recomputed in-instrument")

    # C09 -- the key start disagrees with the clip id start (layout.py:433 copies it)
    a5 = facts("20261009T120020Z-0005")
    d = a5["key"]["started_at_s"] - clip_id_epoch("20261009T120020Z-0005")
    ck("A005 key.started_at_s contradicts its own clip id", abs(d) > 0.0, "delta=%.3f s" % d)
    ck("twin fires C09 on A005 with that delta",
       has("C09", "20261009T120020Z-0005", {"key_started_at_s": a5["key"]["started_at_s"]}) is not None,
       "values carry both starts")

    # C05 -- an interval that ends before it starts
    a7 = facts("20261009T120100Z-0007")
    ck("A007 key ends before it starts", a7["key"]["ended_at_s"] <= a7["key"]["started_at_s"],
       "started=%s ended=%s" % (a7["key"]["started_at_s"], a7["key"]["ended_at_s"]))
    ck("twin fires C05 on A007", has("C05", "20261009T120100Z-0007") is not None, "end <= start")


def q3b(man, twins):
    """The remaining planted shapes: the two-trak trap, the moved path, the absent media."""
    root = man["stores"]["full"]["root"]
    findings = twins["full"].get("findings") or []
    rows = twins["full"].get("rows") or []

    def has(cls, frag, want=None):
        for f in findings:
            if f.get("cls") != cls:
                continue
            if frag not in (f.get("subject") or ""):
                continue
            if want is None:
                return f
            v = f.get("values") or {}
            if all(v.get(k) == val for k, val in want.items()):
                return f
        return None

    def row_of(frag):
        for r in rows:
            if frag in (r.get("dir") or r.get("path") or ""):
                return r
        return None

    # A006 -- a clip whose video and audio traks DISAGREE: the audio must not be read as the clip
    a6 = "20261009T120040Z-0006"
    p6 = os.path.join(cdir(root, a6), "clip.mp4")
    b = open(p6, "rb").read()
    tf = trak_facts(b)
    ms_v = [m for k, m in tf if k == "vide" and m is not None]
    ms_s = [m for k, m in tf if k == "soun" and m is not None]
    ck("A006 carries a vide and a soun trak (the independent reader sees both)",
       len(ms_v) == 1 and len(ms_s) == 1,
       "handlers=" + ",".join(k for k, m in tf) + " ms=" + ",".join(str(m) for k, m in tf))
    ck("A006 the two traks DISAGREE (this is the max() trap)",
       ms_v and ms_s and ms_v[0] != ms_s[0],
       "vide=%s soun=%s" % (ms_v[0] if ms_v else None, ms_s[0] if ms_s else None))
    row = row_of(a6)
    ck("twin row end_candidates names the vide trak, not the longer trak",
       row is not None and any(c.get("source") == "moov" and "vide" in str(c.get("detail", ""))
                              for c in (row.get("end_candidates") or [])),
       "container bucket=" + str(((row or {}).get("container") or {}).get("duration_ms")))
    ck("twin C07 reads the moov VIDEO trak duration, not max(trak)",
       has("C07", a6) is not None and has("C07", a6).get("values", {}).get("container_ms") == ms_v[0],
       "container_ms=" + str((has("C07", a6) or {}).get("values", {}).get("container_ms")))
    ck("twin C08 reads the same moov VIDEO trak duration against the db row",
       has("C08", a6) is not None and has("C08", a6).get("values", {}).get("container_ms") == ms_v[0],
       "container_ms=" + str((has("C08", a6) or {}).get("values", {}).get("container_ms")))
    ck("twin C2TRAK fires on A006 with both durations",
       has("C2TRAK", a6) is not None,
       "values=" + str((has("C2TRAK", a6) or {}).get("values")))

    # A010 -- the clip whose db row LEFT the disk: content_key is UNIQUE, so it must be a stale path
    a10 = "20261009T120130Z-0010"
    key10 = key_at(root, a10) or {}
    db10 = db_rows_of(root).get(key10.get("content_key") or "-", [])
    live = os.path.join(cdir(root, a10), "clip.mp4")
    ck("A010 the db path for that identity is NOT where the clip lives",
       bool(db10) and norm(db10[0]["path"]) != norm(os.path.dirname(live)),
       "db=" + str(db10[0]["path"] if db10 else None) + " live=" + norm(os.path.dirname(live)))
    dbpath = db10[0]["path"] if db10 else ""
    ck("A010 the db-named file is gone from disk (the path moved)",
       bool(dbpath) and not os.path.isfile(dbpath), norm(dbpath))
    ck("A010 the clip itself IS on disk at its clip-id dir (identity survived, the path did not)",
       os.path.isfile(live), norm(live))
    c9 = [x for x in findings if x.get("cls") == "C03" and "20261009T120121Z-0009" in str(x.get("subject"))]
    ck("the OTHER half of the identical pair is also flagged: UNIQUE(content_key) cannot index both",
       any(x.get("name") == "DB ROW ABSENT" for x in c9),
       "; ".join(str(x.get("name")) for x in c9) or "no C03 on A009")
    dk = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    ck("A015: a db row for its identity exists and names a path that was never written",
       bool(db_rows_of(root).get(dk, [])), "db rows for the deadbeef key")
    dead = [x for x in findings if x.get("cls") == "C03" and "deadbeef" in str(x.get("detail") or "")]
    ck("twin C03 names that deadbeef row rather than the clip id", len(dead) >= 1,
       str([x.get("subject") for x in dead]))
    ck("twin C03 PATH MOVED / DB ROW ABSENT fires for A010",
       has("C03", a10) is not None, "C03 on the stale row")

    # A015 -- a db row with no media at all
    a15 = "20261009T120158Z-0015"
    ck("A015 holds no clip.mp4 on disk",
       not os.path.isfile(os.path.join(cdir(root, a15), "clip.mp4")),
       norm(os.path.join(cdir(root, a15), "clip.mp4")))
    dk = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    ck("A015: a db row for its identity exists and names a path that was never written",
       bool(db_rows_of(root).get(dk, [])), "db rows for the deadbeef key")
    dead = [x for x in findings if x.get("cls") == "C03" and "deadbeef" in str(x.get("detail") or "")]
    ck("twin C03 names that deadbeef row rather than the clip id", len(dead) >= 1,
       str([x.get("subject") for x in dead]))

    # the two foreign clips the db mis-declares
    for name, want_ms in (("legacy-2026-09-01.mp4", None), ("db-zero-duration.mp4", None)):
        p = os.path.join(root, "imports", name)
        mine = video_ms_of(p)
        ck("%s this reader derives its video trak duration" % name, mine is not None,
           "video_ms=" + str(mine))
        f = has("C08", name)
        ck("twin C08 on %s agrees with this reader" % name,
           f is not None and (f.get("values") or {}).get("container_ms") == mine,
           "container_ms=" + str((f or {}).get("values", {}).get("container_ms")) + " mine=" + str(mine))


# ---- Q4: the control arms --------------------------------------------------------
def q4(man, twins):
    c, m, f = twins["clean"], twins["mutant"], twins["full"]
    cr, mr, fr = (c.get("counts") or {}), (m.get("counts") or {}), (f.get("counts") or {})
    ck("clean arm: zero red findings", cr.get("findings_red") == 0,
       "findings_red=" + str(cr.get("findings_red")))
    ck("clean arm: exit code 0", c.get("exit_code") == 0, "exit_code=" + str(c.get("exit_code")))
    reds = [x for x in (m.get("findings") or []) if x.get("severity") == "red"]
    ck("mutant arm: exactly one red finding", len(reds) == 1,
       "red=" + str(len(reds)) + " classes=" + ",".join(sorted(set(str(x.get("cls")) for x in reds))))
    if reds:
        ck("mutant arm: the one red is C01", reds[0].get("cls") == "C01",
           "cls=" + str(reds[0].get("cls")))
        ck("mutant arm: it lands on the planted A900 clip",
           str(reds[0].get("subject") or "").endswith("20261009T120015Z-0900"),
           str(reds[0].get("subject")))
    ck("mutant arm: exit code 1", m.get("exit_code") == 1, "exit_code=" + str(m.get("exit_code")))
    ck("full arm: exit code 1", f.get("exit_code") == 1, "exit_code=" + str(f.get("exit_code")))
    ck("full arm: self audit 7 green 0 RED",
       fr.get("audit_green") == 7 and fr.get("audit_red") == 0,
       "green=" + str(fr.get("audit_green")) + " red=" + str(fr.get("audit_red")))
    ck("full arm: the instrument graded its own expectations and none went MISSING",
       (f.get("expectation_checks_failed") or 0) == 0,
       "failed=" + str(f.get("expectation_checks_failed")))
    want_ref = len((man["stores"]["full"].get("expect") or {}).get("REFUSAL") or [])
    got_ref = len([x for x in (f.get("findings") or []) if x.get("cls") == "REFUSAL"])
    ck("full arm: every planted refusal fires (manifest REFUSAL count)", want_ref == got_ref,
       "manifest=" + str(want_ref) + " fired=" + str(got_ref))


def summary():
    print("")
    print("checks=%d failures=%d" % (CHECKS[0], len(FAILS)))
    for f in FAILS:
        print("  RED " + f)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    main()
    sys.exit(summary())