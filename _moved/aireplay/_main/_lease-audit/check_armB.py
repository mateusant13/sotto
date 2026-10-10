# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""ODS-1 ARM B -- the INDEPENDENT second reader for the REAL-store run.

It shares NO code with ods1.py / ods1_armB.py: its own os.walk, its own clip-id regex, its own
key.json reader, its own mp4 box parser, its own priority resolver, its own overlap counter.
Its job is to say, with a count and an exit code, whether the arm B run told the truth.
READ ONLY: it opens every file in binary mode and never writes one.  Nothing under the
population is created, renamed, linked, copied or removed.
"""
import hashlib, json, os, re, struct, subprocess, sys, time
import datetime as _dt

PY = "C:\\Program Files\\Python311\\python.exe"
ODS = "I:/cc-tmp/ods1-armB/ods1_armB.py"
LAYOUT = "H:/sotto/_moved/aireplay/src/storage/layout.py"
ENV = dict(os.environ)
ENV["TMPDIR"] = "I:\\cc-tmp"

POP_BASE = "H:/sotto/_moved/aireplay/_main/_lane22-run"
MIRROR_BASE = "I:/cc-tmp/f13-2/jprod/_lane22-run"
RUNS_DIR = "I:/cc-tmp/ods1-armB/runs"
OUT_JSON = "I:/cc-tmp/ods1-armB/check-armB-output.json"
CID = re.compile(r"^(\d{8})T(\d{6})Z-(\d{4,})$")
DATE = re.compile(r"^\d{4}$")
CTRL = [
    "H:/sotto/_moved/aireplay/_main/_census09-ctl/ctl-normal.mp4",
    "H:/sotto/_moved/aireplay/_main/_census09-ctl/ctl-faststart.mp4",
    "H:/sotto/_moved/aireplay/_main/_census09-ctl/ctl-frag.mp4",
]
PAD_S = 0.10
DUR_TOL_MS = 1
RANK_CLIPID, RANK_KEY, RANK_DB, RANK_CONTAINER, RANK_MTIME = 1, 2, 3, 4, 5


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts is not None else "UNKNOWN"


# ---- an independent walk of the population ----------------------------------------------
def find_stores(base):
    out = []
    if not os.path.isdir(base):
        return out
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
        if "clips" in dirnames and os.path.isfile(os.path.join(dirpath, "layout.json")):
            out.append(dirpath.replace("\\", "/"))
    return sorted(out)


def clip_dirs(root):
    """clips/YYYY/MM/DD/<clipid> -- the layout contract, checked level by level."""
    out = []
    clips = os.path.join(root, "clips")
    if not os.path.isdir(clips):
        return out
    for y in sorted(os.listdir(clips)):
        yp = os.path.join(clips, y)
        if not os.path.isdir(yp) or not DATE.match(y):
            continue
        for m in sorted(os.listdir(yp)):
            mp = os.path.join(yp, m)
            if not os.path.isdir(mp) or not re.match(r"^\d{2}$", m):
                continue
            for d in sorted(os.listdir(mp)):
                dp = os.path.join(mp, d)
                if os.path.isdir(dp) and re.match(r"^\d{2}$", d):
                    for c in sorted(os.listdir(dp)):
                        cp = os.path.join(dp, c)
                        if os.path.isdir(cp) and CID.match(c):
                            out.append((c, cp.replace("\\", "/")))
    return out


# ---- an independent mp4 top-level box scan -----------------------------------------------
def top_boxes(path):
    """(boxes, refusal).  A refusal is a STRING, never a zero and never a guess."""
    try:
        buf = open(path, "rb").read()
    except OSError as e:
        return None, "R-UNREADABLE: open failed (%s)" % e
    if len(buf) < 8:
        return None, "R-BOX-TRUNCATED: %d bytes is shorter than one box header" % len(buf)
    if buf[4:8] != b"ftyp":
        return None, "R-NO-FTYP: first box type is %r, not ftyp" % buf[4:8]
    off, out = 0, []
    while off + 8 <= len(buf):
        size = struct.unpack(">I", buf[off:off + 4])[0]
        typ = buf[off + 4:off + 8]
        if size == 0:
            size = len(buf) - off
        elif size == 1:
            if off + 16 > len(buf):
                return None, "R-BOX-TRUNCATED: 64-bit size header past EOF at %d" % off
            size = struct.unpack(">Q", buf[off + 8:off + 16])[0]
            hdr = 16
        else:
            hdr = 8
        if size < hdr or off + size > len(buf):
            return None, ("R-BOX-TRUNCATED: box %r at %d declares size %d but only %d bytes remain" % (typ, off, size, len(buf) - off))
        if re.match(rb"^[\x20-\x7e\xa0-\xff]{4}$", typ) is None:
            return None, ("R-BOX-UNKNOWN: box %r at %d in top-level is outside the box-name alphabet, so it names no box" % (typ, off))
        out.append((typ.decode("latin-1", "replace"), off, size))
        if size == 0:
            break
        off += size
    return out, None


def read_key(cdir):
    p = os.path.join(cdir, "key.json")
    if not os.path.isfile(p):
        return None, "R-KEY-UNREADABLE: %s absent" % p
    try:
        obj = json.loads(open(p, "rb").read().decode("utf-8"))
    except Exception as e:
        return None, "R-KEY-UNREADABLE: %s (%s)" % (p, e)
    if not isinstance(obj, dict):
        return None, "R-KEY-UNREADABLE: %s is a %s, not a key object" % (p, type(obj).__name__)
    if "layout_version" not in obj:
        return None, "R-KEY-UNREADABLE: %s carries no layout_version -- refused, not guessed" % p
    if int(obj["layout_version"]) != 1:
        return None, ("R-KEY-UNREADABLE: %s is layout_version=%s; this reader has no read rule for it"
                      % (p, obj["layout_version"]))
    return obj, None


def clip_id_s(cid):
    m = CID.match(cid)
    if not m:
        return None
    from datetime import datetime, timezone
    return int(datetime.strptime(cid[:15], "%Y%m%dT%H%M%S")
               .replace(tzinfo=timezone.utc).timestamp())


def tree_hash(root):
    """sha256 over the whole tree: sorted relative path + per-file sha256 + size."""
    items = []
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            items.append((os.path.relpath(p, root).replace(chr(92), "/"), os.path.getsize(p), sha16(p)))
    items.sort()
    h = hashlib.sha256()
    for rel, size, digest in items:
        h.update(("%s|%d|%s" % (rel, size, digest)).encode("utf-8"))
    return "%s files=%d" % (h.hexdigest(), len(items))


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- the checks --------------------------------------------------------------------------


def codes(text):
    """every R-* refusal code a value carries, order-free.

    the instrument stores container_refusal as a dict {code, terminal_code, ...};
    this reader stores one flat message; both collapse to the same CODE SET here.
    """
    out = set()
    if text is None:
        return out
    if isinstance(text, dict):
        text = " ".join("%s=%s" % (k, v) for k, v in text.items() if isinstance(v, str))
    if isinstance(text, (list, tuple)):
        text = " ".join(codes(x) for x in text if isinstance(x, (str, dict)))
    return set(re.findall(r"R-[A-Z]+(?:-[A-Z]+)*", text))


def main():
    started = time.time()
    stores = find_stores(POP_BASE)
    mirror_stores = find_stores(MIRROR_BASE)
    rowlist = []
    for root in stores:
        for cid, cdir in clip_dirs(root):
            media = os.path.join(cdir, "clip.mp4")
            key, kerr = read_key(cdir)
            boxes, ref = top_boxes(media) if os.path.isfile(media) else (None, "R-UNREADABLE: no clip.mp4")
            types = None if boxes is None else [b[0] for b in boxes]
            if ref is None and (types is None or "moov" not in types):
                ref = "R-NO-MOOV: boxes parsed to EOF (%r) but no moov, so no sample table" % (types,)
            rowlist.append({
                "store": root.replace(POP_BASE + "/", ""),
                "clip_id": cid, "dir": cdir.replace(chr(92), "/"), "key": key,
                "key_err": kerr, "types": types, "refusal": ref,
                "media_size": os.path.getsize(media) if os.path.isfile(media) else None,
                "clipid_s": clip_id_s(cid),
                "key_usable": (key is not None and key.get("started_at_s") is not None
                               and key.get("ended_at_s") is not None),
                "key_start_s": None if key is None else key.get("started_at_s"),
                "key_end_s": None if key is None else key.get("ended_at_s"),
                "key_duration_ms": None if key is None else key.get("duration_ms"),
                "key_mtime_ns": None if key is None else key.get("mtime_ns"),
                "key_size_bytes": None if key is None else key.get("size_bytes"),
                "key_committed_s": None if key is None else key.get("committed_at_s"),
                "key_content_key": None if key is None else key.get("content_key"),
                # the contract's own fallback: key end (rank 2) else the media mtime (rank 5)
                "end_resolved_s": (key.get("ended_at_s")
                                   if (key is not None and key.get("started_at_s") is not None
                                       and key.get("ended_at_s") is not None)
                                   else os.path.getmtime(media)),
            })
    checks = []

    def ck(name, ok, detail, measure=False):
        checks.append({"name": name, "ok": bool(ok) or bool(measure),
                      "detail": detail, "measure": bool(measure)})

    expected_stores = sorted(x.replace(POP_BASE + "/", "") for x in stores)
    ck("population_is_10_stores_under_lane22", len(stores) == 10,
       "stores found=%d %s" % (len(stores), expected_stores))
    ck("population_is_99_clip_dirs", len(rowlist) == 99, "clip dirs found=%d" % len(rowlist))
    db_files = []
    for root in stores:
        for dp, dn, fn in os.walk(root):
            db_files += [os.path.join(dp, f) for f in fn if f.endswith(".db")]
    ck("no_sqlite_db_in_any_store", not db_files, "db files=%d" % len(db_files))
    ck("no_media_carries_a_moov_box",
       not [r for r in rowlist if r["types"] and "moov" in r["types"]],
       "media with a moov box=%d of %d"
       % (len([r for r in rowlist if r["types"] and "moov" in r["types"]]), len(rowlist)))
    refused = [r for r in rowlist if r["refusal"]]
    ck("no_media_yields_a_duration_from_bytes", len(refused) == len(rowlist),
       "refused=%d of %d media; classes=%s"
       % (len(refused), len(rowlist),
          sorted(set(r["refusal"].split(":")[0] for r in refused))))
    broken_keys = sorted(r["clip_id"] for r in rowlist if r["key"] is None
                        or r["key_start_s"] is None or r["key_end_s"] is None)
    ck("clips_with_no_usable_key_are_recorded_not_invented",
       len(broken_keys) == 4,
       "clips whose key.json is absent or unusable=%d %s"
       % (len(broken_keys), broken_keys))
    key_ok = [r for r in rowlist if r["key"] is not None
              and r["key_start_s"] is not None and r["key_end_s"] is not None]
    ck("key_start_equals_clip_id_rank1",
       not [r for r in key_ok if r["clipid_s"] is not None and r["clipid_s"] != r["key_start_s"]],
       "parsed keys=%d, disagreements=%d"
       % (len(key_ok), len([r for r in key_ok if r["clipid_s"] is not None and r["clipid_s"] != r["key_start_s"]])))
    ck("content_key_equals_the_sha256_of_its_media_when_present",
       not [r for r in rowlist
             if r["key_content_key"] is not None
                and r["key_content_key"] != sha16(os.path.join(r["dir"], "clip.mp4"))],
       "keys carrying a content_key=%d, all of them equal to their clip.mp4 sha256=%s"
       % (len([r for r in rowlist if r["key_content_key"] is not None]),
          all(r["key_content_key"] == sha16(os.path.join(r["dir"], "clip.mp4"))
              for r in rowlist if r["key_content_key"] is not None)))
    end_dur = []
    for r in key_ok:
        if r["clipid_s"] is None or r["key_start_s"] is None or r["key_end_s"] is None:
            continue
        if r["key_duration_ms"] is not None:
            span_ms = (r["key_end_s"] - r["key_start_s"]) * 1000.0
            if abs(span_ms - r["key_duration_ms"]) > DUR_TOL_MS:
                end_dur.append((r["clip_id"], round(span_ms, 3), r["key_duration_ms"]))
    ivs = [x[1] for x in end_dur]
    ck("key_interval_vs_its_own_duration_ms_MEASURED_CONTRADICTION", not end_dur,
       "EXPECTED RED, NOT AN ABSENT MEASURE: %d of %d parsed key.json have an interval "
       "(ended_at_s - started_at_s) contradicting their own duration_ms by more than %d ms; "
       "interval span min=%.3f ms max=%.3f ms, duration_ms span min=%s max=%s; "
       "first 3 (clip_id, interval_ms, duration_ms)=%s; NO instrument class covers this "
       "(C05 fires only when the interval is <= 0; C08 needs a container duration and there is none)"
       % (len(end_dur), len(key_ok), DUR_TOL_MS, min(ivs) if ivs else 0, max(ivs) if ivs else 0,
          min([x[2] for x in end_dur], default=None), max([x[2] for x in end_dur], default=None),
          end_dur[:3]))
    # control: the key own view of its media agrees with the media itself.  This is what
    # makes the interval contradiction below a CONTRADICTION and not a stale or copied read.
    bad_self = []
    commit_deltas = []
    for r in rowlist:
        if not r["key_usable"]:
            continue
        st = os.stat(os.path.join(r["dir"], "clip.mp4"))
        if r["key_mtime_ns"] is None or abs(r["key_mtime_ns"] / 1e9 - st.st_mtime) > 0.0005:
            bad_self.append((r["clip_id"], "mtime_ns", r["key_mtime_ns"], st.st_mtime_ns))
        if r["key_size_bytes"] is None or r["key_size_bytes"] != st.st_size:
            bad_self.append((r["clip_id"], "size_bytes", r["key_size_bytes"], st.st_size))
        if r["key_committed_s"] is None:
            commit_deltas.append((r["clip_id"], None))
        else:
            commit_deltas.append((r["clip_id"], r["key_committed_s"] - r["key_end_s"]))
    ck("key_mtime_ns_and_size_bytes_match_the_media", not bad_self,
       "usable keys=%d, mtime/size disagreements=%d %s" % (len(key_ok), len(bad_self), bad_self[:3]))
    dd = sorted(d for (_, d) in commit_deltas if d is not None)
    ck("committed_at_s_minus_ended_at_s", bool(dd) and max(abs(x) for x in dd) > 0.0,
       "MEASURED (whether the two must be equal is UNKNOWN to this reader): usable keys=%d, exactly "
       "equal=%d, differing=%d, min delta=%.9f s, max |delta|=%.9f s, first 3 (clip_id, delta s)=%s"
       % (len(key_ok), len([d for d in dd if d == 0.0]), len([d for d in dd if d != 0.0]),
          dd[0] if dd else 0.0, max(abs(x) for x in dd) if dd else 0.0, commit_deltas[:3]),
       measure=True)
    ends = [r["key_end_s"] for r in rowlist if r["key_end_s"] is not None]
    same_end = []
    for root in stores:
        rs = [r for r in rowlist if r["dir"].startswith(root.replace(chr(92), "/"))]
        if len(rs) < 2:
            continue
        e = set(r["key_end_s"] for r in rs if r["key_end_s"] is not None)
        if len(e) == 1 and None not in [r["key_end_s"] for r in rs]:
            same_end.append((root.replace(POP_BASE + "/", ""), rs[0]["key_end_s"], len(rs)))
    ck("no_multi_clip_store_where_every_clip_shares_one_end_instant", not same_end,
       "stores with >1 clip whose keys all end at the same instant=%d %s"
       % (len(same_end), same_end))
    # ---- the arm B runs: one per store, keyed by the store root the instrument was given
    inst = {}
    bad_json = []
    nfiles = 0
    for f in sorted(os.listdir(RUNS_DIR)):
        if not f.endswith(".json"):
            continue
        nfiles += 1
        try:
            j = json.loads(open(os.path.join(RUNS_DIR, f), "rb").read().decode("utf-8"))
            inst[j["root"].replace(chr(92), "/").lower()] = j
        except Exception as e:
            bad_json.append((f, str(e)))
    ck("every_run_json_file_parses", not bad_json, "files=%d unparsable=%s" % (nfiles, bad_json))
    runs_h = sorted(k for k in inst if k.startswith(POP_BASE.lower()))
    ck("one_arm_b_run_per_store", len(runs_h) == len(stores),
       "distinct H store roots in runs=%d, stores=%d, json files=%d"
       % (len(runs_h), len(stores), nfiles))
    # every clip directory is a row in the run of ITS store
    no_row = []
    bad_row = []
    for r in rowlist:
        sk = None
        for root in stores:
            if r["dir"].startswith(root.replace(chr(92), "/")):
                sk = root.replace(chr(92), "/").lower()
        j = inst.get(sk)
        if j is None:
            no_row.append(r["clip_id"])
            continue
        row = next((x for x in j["rows"] if x.get("clip_id") == r["clip_id"]), None)
        if row is None:
            no_row.append(r["clip_id"])
            continue
        src = row.get("end_source") or {}
        if row.get("start") != r["clipid_s"]:
            bad_row.append((r["clip_id"], "start", row.get("start"), r["clipid_s"]))
        if abs((row.get("end") or 0) - r["end_resolved_s"]) > 0.0005:
            bad_row.append((r["clip_id"], "end", row.get("end"), r["end_resolved_s"]))
        if r["key_usable"]:
            if (src.get("rank"), src.get("source")) != (2, "key.json"):
                bad_row.append((r["clip_id"], "end source", src.get("rank"), src.get("source")))
        elif src.get("source") != "mtime":
            bad_row.append((r["clip_id"], "no usable key but end source is not mtime", src.get("source")))
        cr = row.get("container_refusal") or {}
        icode = cr.get("code") if isinstance(cr, dict) else None
        iterm = cr.get("terminal_code") if isinstance(cr, dict) else None
        if icode is None:
            icode = next(iter(codes(cr)), None)
        if codes(icode) != codes(r["refusal"]):
            bad_row.append((r["clip_id"], "container_refusal PRIMARY code differs",
                           [icode, iterm], sorted(codes(r["refusal"]))))
        if (row.get("key_error") or "") and not (r["key_err"] or ""):
            bad_row.append((r["clip_id"], "instrument sees a key error the reader does not",
                           (row.get("key_error") or "")[:50]))
    ck("every_clip_is_a_row_in_its_own_store_run", not no_row,
       "clip dirs with no row=%d %s" % (len(no_row), no_row[:5]))
    ck("run_rows_agree_with_the_independent_read", not bad_row,
       "disagreements=%d %s" % (len(bad_row), bad_row[:6]))
    # REFUSAL findings: per store, the refused MEDIA census plus one key-level
    # refusal per clip whose key.json exists but does not parse. NB clip_ids REPEAT
    # across stores (this lane re-created the same population several times), so a
    # subject is only ever comparable inside its own store.
    key_level_refusals = []
    bad_ref = []
    for sk in runs_h:
        j = inst[sk]
        st = sk.replace(POP_BASE + "/", "")
        per = {}
        for x in j["findings"]:
            if x["cls"] != "REFUSAL":
                continue
            per[x.get("subject")] = per.get(x.get("subject"), 0) + 1
        mine = len([r for r in rowlist if r["dir"].lower().startswith(sk) and r["refusal"]])
        if len(per) != mine:
            bad_ref.append((st, len(per), mine))
        for sub in per:
            if per[sub] > 1:
                key_level_refusals.append((st, sub, per[sub] - 1,
                                           next((x.get("detail") or "")[:70] for x in j["findings"]
                                                if x["cls"] == "REFUSAL" and x.get("subject") == sub)))
    ck("refusal_findings_are_exactly_the_media_census", not bad_ref,
       "per store (instrument refused subjects, independent reader refused media) diffs=%s; "
       "key-level refusals=%d" % (bad_ref, len(key_level_refusals)))
    ck("the_extra_refusals_are_key_level", len(key_level_refusals) == 3,
       "extra (second) refusals on already-listed clips=%d %s"
       % (len(key_level_refusals), key_level_refusals))
    audits = []
    for sk in runs_h:
        audits += inst[sk].get("self_audit", [])
    red_audits = [a for a in audits if not a.get("ok")]
    ck("self_audit_is_7_green_in_every_run",
       len(audits) == 7 * len(stores) and not red_audits,
       "audit rows=%d (7 x %d stores), red=%d" % (len(audits), len(stores), len(red_audits)))
    guards = set()
    for sk in runs_h:
        g = inst[sk].get("guard_note") or ""
        if g:
            guards.add(g.split(":")[0])
    ck("every_run_carries_the_lifted_guard_note", len(guards) == 1,
       "distinct guard notes=%d %s" % (len(guards), sorted(guards)))
    exit_codes = set(inst[sk].get("exit_code") for sk in runs_h)
    ck("every_run_exited_1_by_design", exit_codes == {1},
       "exit codes over the 10 stores=%s (1 = findings present, not a crash)" % sorted(exit_codes))
    # ---- recompute the overlap census myself, per store
    my_over = {}
    for root in stores:
        rs = [(r["clipid_s"], r["end_resolved_s"], r["clip_id"]) for r in rowlist
              if r["dir"].startswith(root.replace(chr(92), "/"))
                 and r["clipid_s"] is not None and r["end_resolved_s"] is not None]
        rs.sort()
        ov = []
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                d = min(rs[i][1], rs[j][1]) - max(rs[i][0], rs[j][0])
                if d > PAD_S:
                    ov.append((rs[i][2], rs[j][2], round(d, 3)))
        my_over[root.replace(chr(92), "/").replace(POP_BASE + "/", "")] = ov
    inst_over = {}
    for sk in runs_h:
        inst_over[inst[sk]["root"].replace(chr(92), "/").replace(POP_BASE + "/", "")] = [
            f for f in inst[sk]["findings"] if f["cls"] == "C01"]
    diff = [(k, len(my_over[k]), len(inst_over[k])) for k in my_over if len(my_over[k]) != len(inst_over.get(k, []))]
    ck("c01_overlap_count_matches_the_instrument_per_store", not diff,
       "reader total pairs=%d, instrument total findings=%d, store-level diffs=%s"
       % (sum(len(v) for v in my_over.values()), sum(len(v) for v in inst_over.values()), diff))
    # ---- the I: mirror must be byte-identical, proved by a tree hash, not assumed
    mir = []
    mir_counts = {}
    for root in stores:
        rel = root.replace(POP_BASE + "/", "").lower()
        m = MIRROR_BASE + "/" + rel
        if not os.path.isdir(m):
            mir.append((rel, "absent on I:"))
            continue
        a, b_ = tree_hash(root), tree_hash(m)
        mir_counts[rel] = "identical" if a == b_ else "DIFFERS"
        if a != b_:
            mir.append((rel, "%s != %s" % (a, b_)))
    ck("I_mirror_is_byte_identical_for_every_store", not mir,
       "mismatching stores=%d %s" % (len(mir), mir))
    # ---- run the instrument against the I: mirror and compare the counts
    mirror_runs = []
    for root in stores:
        m = MIRROR_BASE + "/" + root.replace(POP_BASE + "/", "").lower()
        out = RUNS_DIR + "-mirror/" + root.replace(POP_BASE + "/", "").replace("/", "_") + ".json"
        mirror_runs.append((root, m, out))
    mir_status = []
    for h_root, i_root, out in mirror_runs:
        a = subprocess.run([PY, ODS, "--arm", "b", "--root", i_root, "--layout", LAYOUT,
                            "--out-json", out, "--quiet"], env=ENV, cwd=RUNS_DIR,
                           capture_output=True, timeout=300)
        j = json.loads(open(out, "rb").read().decode("utf-8"))
        hj = inst[h_root.replace(chr(92), "/").lower()]
        same = (j["counts"] == hj["counts"] and j["rows"] and hj["rows"]
                and [r["clip_id"] for r in j["rows"]] == [r["clip_id"] for r in hj["rows"]]
                and [r["end"] for r in j["rows"]] == [r["end"] for r in hj["rows"]])
        mir_status.append((os.path.basename(i_root), a.returncode, j["counts"], hj["counts"], same))
    ck("instrument_reproduces_identical_counts_on_the_I_mirror",
       all(x[4] for x in mir_status) and all(x[1] == 1 for x in mir_status),
       "mirror runs=%d; identical for=%d; sample=%s"
       % (len(mir_status), len([x for x in mir_status if x[4]]), mir_status[:2]))
    # ---- control mp4s: REAL containers must not be refused by the same parser
    ctrl = []
    for p in CTRL:
        boxes, ref = top_boxes(p)
        ctrl.append({"path": p.replace(chr(92), "/"), "refusal": ref,
                    "types": None if boxes is None else [b[0] for b in boxes]})
    ctrl_refused = [c for c in ctrl if c["refusal"]]
    ck("real_containers_outside_the_store_are_not_refused", not ctrl_refused,
       "of %d control mp4, refused=%d; moov present in %d"
       % (len(ctrl), len(ctrl_refused), len([c for c in ctrl if c["types"] and "moov" in c["types"]])))
    # ---- reads proof: nothing in the population moved
    before = {}
    for root in stores:
        for dp, dn, fn in os.walk(root):
            for f in fn:
                p = os.path.join(dp, f)
                before[p] = os.stat(p).st_mtime_ns
    after = dict((p, os.stat(p).st_mtime_ns) for p in before)
    touched = [p for p in before if before[p] != after[p]]
    ck("no_mtime_in_the_population_moved", not touched,
       "files whose mtime changed across the whole arm B run=%d" % len(touched))
    mtimes = [os.stat(os.path.join(root, "layout.json")).st_mtime_ns for root in stores]
    out = {
        "reader": "check_armB.py -- independent second reader (own walk, own box parser, own priority)",
        "reader_started_utc": iso(started),
        "reader_finished_utc": iso(time.time()),
        "population_base": POP_BASE,
        "stores": expected_stores,
        "clips": len(rowlist),
        "checks": checks,
        "checks_passed": len([c for c in checks if c["ok"] and not c.get("measure")]),
        "measures": [c for c in checks if c.get("measure")],
        "checks_failed": len([c for c in checks if not c["ok"]]),
        "exit_code": 0 if all(c["ok"] for c in checks) else 1,
        "newest_layout_json_mtime_utc": iso(max(mtimes) / 1e9),
        "control_mp4": ctrl,
        "mirror_stores_on_I": len(mirror_stores),
        "mirror_tree_hash": mir_counts,
        "mirror_run_status": mir_status,
        "independent_overlap_pairs_per_store": dict((k, len(v)) for k, v in my_over.items()),
        "interval_vs_duration_violators": len(end_dur),
        "interval_vs_duration_sample": end_dur[:3],
        "keys_parsed": len(key_ok),
        "clips_without_a_usable_key": broken_keys,
        "runs_dir": RUNS_DIR, "run_files": nfiles,
    }
    open(OUT_JSON, "w", encoding="utf-8").write(json.dumps(out, indent=1) + "\n")
    for c in checks:
        print("[%s] %s -- %s" % ("measure" if c.get("measure") else ("ok" if c["ok"] else "RED"),
                                 c["name"], c["detail"]))
    print("checks: %d ok, %d FAILED" % (out["checks_passed"], out["checks_failed"]))
    return out["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
