# _census09-probe.py -- lane 09 (library census)
# HEADER-ONLY probe of every video file found by _census09-enum.py.
#
# What it does per file, and nothing else:
#   P1  ffprobe -v error  -> container, duration, bitrate, resolution, codec, streams
#   P2  ffprobe -v trace  -> the mov demuxer's OWN atom trace; the token
#                            type:'mvex' parent:'moov' is the DEFINITION of a
#                            fragmented MP4 (ISO/IEC 14496-12). The process is
#                            KILLED as soon as the token is seen, so a fragmented
#                            file costs milliseconds instead of a full moof walk.
#
# It never decodes: no -show_frames, no -count_frames, no -show_packets.
# It never writes to the video, never copies it, never moves it, never renames it.
# ONE reader at a time (single-threaded, files in enumeration order).
import os, sys, json, time, subprocess, shutil, collections, statistics

HERE = r"H:\aireplay\_main"
LOG = os.path.join(HERE, "census09-probe.log")
STOP = os.path.join(HERE, "census09-probe.STOP")

CREATENOWINDOW = 0x08000000

P1_ENTRIES = (
    "format=format_name,format_long_name,duration,size,bit_rate,nb_streams:"
    "format_tags=major_brand,compatible_brands,encoder,creation_time:"
    "stream=index,codec_type,codec_name,codec_long_name,profile,width,height,"
    "pix_fmt,level,r_frame_rate,avg_frame_rate,time_base,nb_frames,duration,"
    "bit_rate,channels,channel_layout,sample_rate,sample_fmt,color_transfer,"
    "color_primaries,color_space:"
    "stream_disposition=default,attached_pic"
)

def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run(cmd, timeout):
    """Run a command with no window, capture stdout+stderr, hard timeout."""
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout, creationflags=CREATENOWINDOW)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None, "", "TIMEOUT after %ss" % timeout
    except OSError as ex:
        return None, "", "OSError: %s" % ex

def probe_meta(ffprobe, path, timeout=60):
    t = time.perf_counter()
    rc, out, err = run([ffprobe, "-v", "error", "-of", "json",
                        "-show_entries", P1_ENTRIES, path], timeout)
    dt = time.perf_counter() - t
    if rc is None:
        return None, dt, err.strip()
    if rc != 0:
        return None, dt, (err.strip() or ("rc=%d" % rc))
    try:
        return json.loads(out), dt, err.strip()
    except ValueError as ex:
        return None, dt, "json: %s" % ex

def probe_frag(ffprobe, path, timeout=30):
    """Trace the mov atom chain, kill on the mvex/moof token. Returns (verdict, seconds, detail)."""
    t = time.perf_counter()
    try:
        p = subprocess.Popen([ffprobe, "-v", "trace", "-show_entries",
                              "format=format_name", path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             creationflags=CREATENOWINDOW)
    except OSError as ex:
        return "probe-failed", time.perf_counter() - t, str(ex)
    verdict, detail = None, ""
    try:
        assert p.stderr is not None
        while True:
            if time.perf_counter() - t > timeout:
                verdict, detail = "trace-timeout", "no mvex/moof within %ss" % timeout
                break
            line = p.stderr.readline()
            if not line:
                break
            s = line.decode("utf-8", "replace")
            if "type:'mvex'" in s:
                verdict, detail = "fragmented", s.strip()
                break
            if "type:'moof'" in s:
                verdict, detail = "fragmented", s.strip()
                break
        if verdict is None:
            verdict = "not-fragmented"
    finally:
        try:
            p.kill()
        except OSError:
            pass
        try:
            p.wait(timeout=5)
        except Exception:
            pass
        try:
            p.stderr.close()
        except Exception:
            pass
    return verdict, time.perf_counter() - t, detail

def main():
    if len(sys.argv) < 3:
        print("usage: _census09-probe.py <enum.json> <out.jsonl> [--limit N] [--resume]")
        return 2
    enum_json, out_jsonl = sys.argv[1], sys.argv[2]
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        log("FATAL ffprobe not on PATH")
        return 2

    with open(enum_json, encoding="utf-8") as f:
        doc = json.load(f)
    files = doc["files"]
    if limit:
        files = files[:limit]

    done = set()
    if "--resume" in sys.argv and os.path.exists(out_jsonl):
        with open(out_jsonl, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["path"])
                except Exception:
                    pass
        log("resume: %d file(s) already probed" % len(done))

    log("probe start: %d file(s), ffprobe=%s, threads=1" % (len(files), ffprobe))
    t_start = time.perf_counter()
    n = ok = fail = frag = 0
    with open(out_jsonl, "a", encoding="utf-8") as out:
        for f in files:
            if os.path.exists(STOP):
                log("STOP file present -> exiting cleanly at %d/%d" % (n, len(files)))
                break
            path = f["path"]
            n += 1
            if path in done:
                continue
            row = {"path": path, "size_enum": f["size"], "mtime": f["mtime"]}
            meta, t1, err1 = probe_meta(ffprobe, path)
            row["t_meta"] = round(t1, 4)
            if meta is None:
                row["ok"] = False
                row["error"] = err1[:500]
                fail += 1
            else:
                row["ok"] = True
                ok += 1
                fmt = meta.get("format", {}) or {}
                streams = meta.get("streams", []) or []
                row["format_name"] = fmt.get("format_name")
                row["format_long_name"] = fmt.get("format_long_name")
                row["tags"] = fmt.get("tags") or {}
                try:
                    row["duration"] = float(fmt.get("duration"))
                except (TypeError, ValueError):
                    row["duration"] = None
                try:
                    row["bit_rate"] = int(fmt.get("bit_rate"))
                except (TypeError, ValueError):
                    row["bit_rate"] = None
                try:
                    row["size_probe"] = int(fmt.get("size"))
                except (TypeError, ValueError):
                    row["size_probe"] = None
                v = next((s for s in streams if s.get("codec_type") == "video"), None)
                a = next((s for s in streams if s.get("codec_type") == "audio"), None)
                row["n_audio"] = sum(1 for s in streams if s.get("codec_type") == "audio")
                row["n_video"] = sum(1 for s in streams if s.get("codec_type") == "video")
                if v:
                    row["v_codec"] = v.get("codec_name")
                    row["v_profile"] = v.get("profile")
                    row["w"] = v.get("width")
                    row["h"] = v.get("height")
                    row["v_pix_fmt"] = v.get("pix_fmt")
                    row["v_fps"] = v.get("avg_frame_rate") or v.get("r_frame_rate")
                    row["v_bit_rate"] = _int(v.get("bit_rate"))
                    row["v_nb_frames"] = _int(v.get("nb_frames"))
                    row["v_duration"] = _float(v.get("duration"))
                    row["v_color_primaries"] = v.get("color_primaries")
                    row["v_color_transfer"] = v.get("color_transfer")
                    row["v_color_space"] = v.get("color_space")
                if a:
                    row["a_codec"] = a.get("codec_name")
                    row["a_channels"] = a.get("channels")
                    row["a_sample_rate"] = _int(a.get("sample_rate"))
                    row["a_bit_rate"] = _int(a.get("bit_rate"))
                    row["a_duration"] = _float(a.get("duration"))
            # fragmentation: only meaningful for the ISO-BMFF family
            fn = (row.get("format_name") or "")
            if "mp4" in fn or "mov" in fn:
                fv, t2, detail = probe_frag(ffprobe, path)
                row["frag"] = fv
                row["frag_detail"] = detail[:200]
                row["t_frag"] = round(t2, 4)
                if fv == "fragmented":
                    frag += 1
            else:
                row["frag"] = "n/a"
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            if n % 25 == 0:
                el = time.perf_counter() - t_start
                log("  %d/%d ok=%d fail=%d frag=%d  %.2f s/file  elapsed=%.0fs"
                    % (n, len(files), ok, fail, frag, el / max(n, 1), el))
    el = time.perf_counter() - t_start
    log("DONE n=%d ok=%d fail=%d frag=%d elapsed=%.1fs (%.3f s/file) -> %s"
        % (n, ok, fail, frag, el, el / max(n, 1), out_jsonl))
    return 0

def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None

def _float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

if __name__ == "__main__":
    sys.exit(main())
