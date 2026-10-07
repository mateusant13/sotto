# _census09-analyze.py -- lane 09 (library census)
# Reads the probe JSONL and publishes the DISTRIBUTION (not the mean).
import os, sys, json, collections, datetime

def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[i]

def dist(vals):
    v = sorted(x for x in vals if x is not None and x > 0)
    if not v:
        return None
    return {
        "n": len(v), "min": v[0],
        "p10": pct(v, .10), "p25": pct(v, .25), "median": pct(v, .50),
        "p75": pct(v, .75), "p90": pct(v, .90), "p99": pct(v, .99),
        "max": v[-1],
        "mean": round(sum(v) / len(v), 2),
    }

def bucket(w, h):
    if not w or not h:
        return "unknown"
    px = w * h
    if w >= 3840 or h >= 2160:
        return "4K+"
    if w >= 2560 or h >= 1440:
        return "1440p"
    if w >= 1920 or h >= 1080:
        return "1080p"
    if w >= 1280 or h >= 720:
        return "720p"
    if w >= 640:
        return "SD"
    return "tiny"

def which_drive(path):
    return os.path.splitdrive(path)[0].upper() + "\\"

def main():
    rows = []
    for fn in sys.argv[1:]:
        with open(fn, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    ok = [r for r in rows if r.get("ok")]
    bad = [r for r in rows if not r.get("ok")]

    out = {"files_probed": len(rows), "files_ok": len(ok), "files_failed": len(bad)}

    # ---- drive split -------------------------------------------------------
    per_drive = collections.defaultdict(lambda: {"files": 0, "bytes": 0, "seconds": 0.0})
    for r in rows:
        d = which_drive(r["path"])
        per_drive[d]["files"] += 1
        per_drive[d]["bytes"] += r.get("size_enum") or 0
    for r in ok:
        d = which_drive(r["path"])
        per_drive[d]["seconds"] += r.get("duration") or 0
    out["per_drive"] = {k: v for k, v in sorted(per_drive.items())}

    # ---- totals ------------------------------------------------------------
    tot_bytes = sum((r.get("size_enum") or 0) for r in ok)
    tot_sec = sum((r.get("duration") or 0) for r in ok)
    out["total_bytes"] = tot_bytes
    out["total_gb"] = round(tot_bytes / 1e9, 2)          # decimal GB
    out["total_gib"] = round(tot_bytes / 1024 ** 3, 2)
    out["total_seconds"] = round(tot_sec, 1)
    out["total_hours"] = round(tot_sec / 3600, 2)
    out["no_duration"] = sum(1 for r in ok if not r.get("duration"))

    # ---- bitrate -----------------------------------------------------------
    out["container_bitrate_bps"] = dist([r.get("bit_rate") for r in ok])
    out["video_bitrate_bps"] = dist([r.get("v_bit_rate") for r in ok])
    out["audio_bitrate_bps"] = dist([r.get("a_bit_rate") for r in ok])
    if tot_sec > 0:
        out["library_average_bitrate_bps"] = round(tot_bytes * 8 / tot_sec, 0)
        out["library_average_mbps"] = round(tot_bytes * 8 / tot_sec / 1e6, 3)

    # ---- resolution / codec / container -----------------------------------
    rb = collections.Counter(bucket(r.get("w"), r.get("h")) for r in ok)
    out["resolution_buckets"] = dict(rb.most_common())
    out["codec_video"] = dict(collections.Counter(r.get("v_codec") for r in ok).most_common())
    out["codec_audio"] = dict(collections.Counter(r.get("a_codec") for r in ok).most_common())
    out["container"] = dict(collections.Counter(r.get("format_name") for r in ok).most_common())
    out["fps"] = dict(collections.Counter(r.get("v_fps") for r in ok).most_common(15))

    # ---- fragmentation (the 08 UNKNOWN #1) --------------------------------
    frags = collections.Counter(r.get("frag") for r in rows)
    out["fragmentation"] = dict(frags)
    out["fragmented_detail"] = [
        {"path": r["path"], "size": r.get("size_enum"), "duration": r.get("duration"),
         "bit_rate": r.get("bit_rate"), "w": r.get("w"), "h": r.get("h"),
         "v_codec": r.get("v_codec"), "tags": r.get("tags")}
        for r in rows if r.get("frag") == "fragmented"
    ]
    out["fragmented_bytes"] = sum((r.get("size_enum") or 0) for r in rows if r.get("frag") == "fragmented")
    out["fragmented_hours"] = round(sum((r.get("duration") or 0)
                                        for r in rows if r.get("frag") == "fragmented") / 3600, 2)

    # ---- probe cost (the REAL seek latency of this drive, one reader) -----
    out["t_meta_s"] = dist([r.get("t_meta") for r in rows])
    out["t_frag_s"] = dist([r.get("t_frag") for r in rows if r.get("t_frag")])
    # per-drive header cost, which is what the HDD's seek behaviour shows
    for d in list(per_drive):
        per_drive[d]["t_meta_s"] = dist([r.get("t_meta") for r in rows
                                         if which_drive(r["path"]) == d])

    # ---- audio presence (what the ASR pass actually needs) ----------------
    out["files_with_audio"] = sum(1 for r in ok if (r.get("n_audio") or 0) > 0)
    out["files_without_audio"] = sum(1 for r in ok if (r.get("n_audio") or 0) == 0)
    out["audio_seconds"] = round(sum((r.get("a_duration") or 0) for r in ok), 1)

    # ---- largest files / longest durations --------------------------------
    out["top_sizes"] = [{"path": r["path"], "gb": round((r.get("size_enum") or 0) / 1e9, 2),
                         "hours": round((r.get("duration") or 0) / 3600, 2),
                         "mbps": round((r.get("bit_rate") or 0) / 1e6, 2)}
                        for r in sorted(ok, key=lambda r: -(r.get("size_enum") or 0))[:10]]
    out["top_durations"] = [{"path": r["path"], "hours": round((r.get("duration") or 0) / 3600, 2),
                             "gb": round((r.get("size_enum") or 0) / 1e9, 2)}
                            for r in sorted(ok, key=lambda r: -(r.get("duration") or 0))[:10]]

    out["failures"] = [{"path": r["path"], "error": r.get("error")} for r in bad]

    # ---- mtime spread ------------------------------------------------------
    years = collections.Counter()
    for r in ok:
        try:
            years[datetime.datetime.fromtimestamp(r["mtime"]).year] += 1
        except Exception:
            pass
    out["by_year_mtime"] = dict(sorted(years.items()))

    json.dump(out, open(sys.argv[-1] + ".summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
