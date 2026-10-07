# _census09-enum.py -- lane 09 (library census)
# Enumerate video files BY EXTENSION on every fixed drive. METADATA ONLY:
# os.scandir + stat. No file is opened, read, decoded or modified.
# Output: _main/census09-enum.json  (files[] + per-directory rollup + per-drive rollup)
import os, sys, json, time, collections

LOG = r"H:\aireplay\_main\census09-enum.log"

# One list, sorted, so the census is reproducible from this file alone.
VIDEO_EXT = {
    # containers
    ".mp4", ".m4v", ".mkv", ".webm", ".avi", ".mov", ".qt", ".wmv", ".asf",
    ".flv", ".f4v", ".mpg", ".mpeg", ".mpe", ".mpv", ".m2v", ".m1v", ".m2p",
    ".ts", ".m2ts", ".mts", ".tp", ".trp", ".vob", ".ifo", ".rm", ".rmvb",
    ".divx", ".3gp", ".3g2", ".ogv", ".ogm", ".mxf", ".dv", ".dav", ".mod",
    ".tod", ".vro", ".svi", ".nsv", ".wtv", ".dvr-ms", ".amv", ".bik", ".smk",
    ".fli", ".flc", ".roq", ".y4m", ".yuv", ".nut", ".rec", ".ts2",
    # raw/transport elementary streams
    ".h264", ".h265", ".hevc", ".av1", ".264", ".265", ".vvc", ".m4s",
    # screen/stream captures people keep around
    ".mkv3d", ".pds", ".veg",
}

def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def drives():
    """Fixed drives with a letter, from the volume list (no network, no removable)."""
    out = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = letter + ":\\"
        if os.path.isdir(root):
            out.append(root)
    return out

def walk(root):
    """Iterative scandir walk. Returns (files, dirs, denied)."""
    files, dirs, denied = [], [], []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            dirs.append(e.path)
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            ext = os.path.splitext(e.name)[1].lower()
                            if ext in VIDEO_EXT:
                                try:
                                    st = e.stat(follow_symlinks=False)
                                    files.append({
                                        "path": e.path,
                                        "size": st.st_size,
                                        "mtime": int(st.st_mtime),
                                    })
                                except OSError as ex:
                                    denied.append([e.path, "stat:%s" % ex])
                    except OSError as ex:
                        denied.append([e.path, "entry:%s" % ex])
        except (PermissionError, OSError) as ex:
            denied.append([d, "scandir:%s" % ex])
    return files, dirs, denied

def main():
    t0 = time.time()
    all_files, per_drive, all_denied = [], {}, []
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    roots = only if only else drives()
    tag = "".join(r[0] for r in roots)
    out = r"H:\aireplay\_main\census09-enum-%s.json" % tag
    for root in roots:
        log("walk %s ..." % root)
        t1 = time.time()
        files, dirs, denied = walk(root)
        dt = time.time() - t1
        per_drive[root] = {
            "files": len(files), "dirs_seen": len(dirs), "denied": len(denied),
            "bytes": sum(f["size"] for f in files), "seconds": round(dt, 1),
        }
        all_files.extend(files)
        all_denied.extend(denied)
        log("  %s -> %d video file(s), %d dir(s), %d denied, %.1f s"
            % (root, len(files), len(dirs), len(denied), dt))

    # per-directory rollup (the folder list with counts the brief asks for)
    roll = collections.Counter()
    rollbytes = collections.Counter()
    for f in all_files:
        d = os.path.dirname(f["path"])
        roll[d] += 1
        rollbytes[d] += f["size"]
    dirs_sorted = [{"dir": d, "count": roll[d], "bytes": rollbytes[d]}
                   for d in sorted(roll, key=lambda d: (-roll[d], d))]

    # extension rollup
    ext = collections.Counter()
    extbytes = collections.Counter()
    for f in all_files:
        e = os.path.splitext(f["path"])[1].lower()
        ext[e] += 1
        extbytes[e] += f["size"]

    doc = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "host": os.environ.get("COMPUTERNAME"),
        "extensions_scanned": sorted(VIDEO_EXT),
        "roots": roots,
        "per_drive": per_drive,
        "total_files": len(all_files),
        "total_bytes": sum(f["size"] for f in all_files),
        "by_extension": [{"ext": e, "count": ext[e], "bytes": extbytes[e]}
                         for e in sorted(ext, key=lambda e: -ext[e])],
        "by_directory": dirs_sorted,
        "denied": all_denied[:2000],
        "denied_total": len(all_denied),
        "files": all_files,
        "seconds_total": round(time.time() - t0, 1),
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    log("DONE files=%d bytes=%d dirs=%d denied=%d in %.1f s -> %s"
        % (len(all_files), doc["total_bytes"], len(dirs_sorted),
           len(all_denied), doc["seconds_total"], out))

if __name__ == "__main__":
    main()
