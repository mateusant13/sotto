"""ARM B census (READ ONLY).

Lists every clip library root this instrument can find on this host: a directory R
such that R/clips holds at least one clip-id directory at clips/YYYY/MM/DD/<clipid>.
For each root it records PATH, POPULATION (what was read) and WINDOW (ISO instant
of the read) and never opens anything for writing.

No sha, no byte content: this is the population list only.
"""
import os, re, sys, json, datetime

CLIP_RE = re.compile(r"^(\d{8})T(\d{6})Z-(\d{4,})$")
YEAR_RE = re.compile(r"^\d{4}$")
MONTH_RE = re.compile(r"^\d{2}$")
DAY_RE = re.compile(r"^\d{2}$")

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def human(n):
    return datetime.datetime.fromtimestamp(n, datetime.timezone.utc).isoformat()

SKIP = {".git", "node_modules", "AppData", "$RECYCLE.BIN", "System Volume Information"}

def safe_listdir(p):
    try:
        return sorted(os.listdir(p))
    except OSError:
        return []

def count_clip_dirs(clips, limit=1):
    n = 0
    for y in safe_listdir(clips):
        if YEAR_RE.match(y) is None:
            continue
        for m in safe_listdir(os.path.join(clips, y)):
            if MONTH_RE.match(m) is None:
                continue
            for d in safe_listdir(os.path.join(clips, y, m)):
                if DAY_RE.match(d) is None:
                    continue
                for cid in safe_listdir(os.path.join(clips, y, m, d)):
                    if CLIP_RE.match(cid):
                        n += 1
                        if n >= limit:
                            return n
    return n

def roots_under(base, max_depth=8):
    found = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        rel = os.path.relpath(dirpath, base)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            dirnames[:] = []
        if "clips" in dirnames:
            cand = os.path.join(dirpath, "clips")
            if count_clip_dirs(cand) > 0:
                found.append(dirpath)
    return sorted(found)

def describe(root):
    clips = os.path.join(root, "clips")
    n_clip = 0; n_key = 0; n_mp4 = 0; n_partial = 0; n_thumb = 0; n_transcript = 0
    total = 0; newest = 0.0; oldest = None
    db = []
    for dirpath, dirnames, filenames in os.walk(clips):
        for d in dirnames:
            if CLIP_RE.match(d):
                n_clip += 1
        for f in filenames:
            p = os.path.join(dirpath, f)
            try:
                s = os.lstat(p)
            except OSError:
                continue
            total += s.st_size
            if s.st_mtime > newest:
                newest = s.st_mtime
            if oldest is None or s.st_mtime < oldest:
                oldest = s.st_mtime
            if f == "key.json":
                n_key += 1
            elif f == "clip.mp4":
                n_mp4 += 1
            elif f == ".partial":
                n_partial += 1
            elif f == "thumb.jpg":
                n_thumb += 1
            elif f == "transcript.json":
                n_transcript += 1
            if f.endswith((".sqlite", ".sqlite3", ".db")):
                db.append(os.path.join(dirpath, f))
    return {"clip_dirs": n_clip, "key_json": n_key, "clip_mp4": n_mp4,
            "partial_markers": n_partial, "thumb_jpg": n_thumb,
            "transcript_json": n_transcript, "bytes_under_clips": total,
            "newest_mtime_utc": human(newest) if newest else "UNKNOWN",
            "oldest_mtime_utc": human(oldest) if oldest else "UNKNOWN",
            "db_files_under_clips": db,
            "layout_json_present": os.path.isfile(os.path.join(root, "layout.json")),
            "root_entries": sorted(safe_listdir(root))}

def main():
    bases = sys.argv[1:] or ["H:/sotto/_moved/aireplay", "I:/cc-tmp"]
    all_roots = []
    for b in bases:
        for r in roots_under(b):
            all_roots.append(r)
    out = {"census_started_utc": now_iso(), "bases": bases, "stores": []}
    for r in all_roots:
        w = now_iso()
        d = describe(r)
        d["path"] = r
        d["window_read_utc"] = w
        out["stores"].append(d)
    out["census_finished_utc"] = now_iso()
    out["store_count"] = len(all_roots)
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()