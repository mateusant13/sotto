#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLIP-TO-ASR gate -- build order step 5, the indexing half, lane B.

ONE command runs BOTH colours:

    python test_clip_to_asr.py
        GREEN arm : the REAL src/pipeline/clip_to_asr.py, on a REAL clip.
                    ARMS A (video row AND >=1 speech row, provenance speech),
                    C (idempotence: the second run changes NOTHING),
                    C2 (identity is content_key, never the path),
                    D1 (ASR worker dies: loud status, video row survives,
                        speech channel empty and it says so),
                    D2 (ASR worker STALLS: the video row is already readable
                        on a SECOND connection while the stall is still alive,
                        so the capture path is never blocked),
                    E (nothing fabricated: no visual / ocr / embedding rows),
                    V (a VIDEO-ONLY clip is REFUSED, never given a fake pass),
                    X (a CHANGED transcript for a minted seg_id is refused,
                        never silently overwritten),
                    W (no visible console window, sampled at our own cadence).
        RED arm    : a COPY of clip_to_asr.py with the speech-row preflight
                    REMOVED (precisely the fix this lane shipped).  The copy
                    must stay green on its FIRST run and must FAIL on its
                    SECOND run with the FTS5 'delete' trigger error -- which
                    is the whole reason write_speech_row exists.

Every single check prints the number that decided it.  The final words are
    CLIPASR-GATE PASS    (the green arm: every arm green, zero checks failed)
    CLIPASR-GATE-NEG PASS (the red arm: every control green, the predicted
                          failure fired exactly where it was predicted)
and the conjunction is
    CLIPASR-FINAL PASS
There is NO skip: a missing subject (fixture, model, ffmpeg) is a REFUSAL
(exit 2) that says what is missing, never a silent pass.

Run it from its own src/ directory (the module resolves its repo root from
__file__) with TMPDIR pointed at I:\cc-tmp.
"""

import argparse
import ctypes
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent
for _p in (str(_SRC),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from index import store                     # noqa: E402
from pipeline import clip_to_asr as C       # noqa: E402

GATE = "CLIPASR-GATE"
NEG_FILE = "_clipasr_neg_copy.py"

DEFAULT_CLIP = Path(r"I:/cc-tmp/clipasr/fixture-15s.mp4")
DEFAULT_WORK = Path(r"I:/cc-tmp/clipasr/gate")
VIDEOONLY_CLIP = DEFAULT_WORK / "fixture-videoonly.mp4"

TABLES = ("video", "segment", "transcript", "text_fts", "ocr", "embedding",
          "marker", "index_meta")

HAS_API = hasattr(os, "add_dll_directory")


class Refuse(Exception):
    """The gate refuses to run rather than report a fabricated verdict."""


class Arm(object):
    """One acceptance arm: a named bag of checks that prints as it goes."""

    def __init__(self, name):
        self.name = name
        self.checks = 0
        self.failed = 0
        self.lines = []

    def ok(self, what, cond, detail=""):
        self.checks += 1
        if not cond:
            self.failed += 1
        self.lines.append("  %s %-46s %s" % ("PASS" if cond else "FAIL",
                                             what, detail))
        self.flush()
        return bool(cond)

    def note(self, line):
        self.lines.append("       " + line)
        self.flush()

    def flush(self):
        if self.lines:
            sys.stdout.write("\n".join(self.lines) + "\n")
            sys.stdout.flush()
            self.lines = []

    @property
    def green(self):
        return self.failed == 0


# ---------------------------------------------------------------------------
# independent instruments (the gate does not trust the module it is testing)
# ---------------------------------------------------------------------------

def counts(conn):
    out = {}
    for t in TABLES:
        out[t] = conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
    return out


def table_hash(conn, table):
    """Rows + a canonical sha256 of one table, read with a fresh query."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(" + table + ")")]
    rows = conn.execute("SELECT " + ",".join('"' + c + '"' for c in cols)
                        + ' FROM "' + table + '" ORDER BY rowid').fetchall()
    norm = [[None if v is None else (v if isinstance(v, (int, float))
                                     else str(v)) for v in r] for r in rows]
    blob = json.dumps({"table": table, "columns": cols, "rows": norm},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"rows": len(rows),
            "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest()}


def check_no_fabrication(arm, conn, tag):
    """ARM E, applied after EVERY arm: the index holds speech rows only."""
    n = counts(conn)
    arm.ok("E %s: embedding table empty (no visual row fabricated)" % tag,
           n["embedding"] == 0, "rows=%d" % n["embedding"])
    arm.ok("E %s: ocr table empty (no ocr row fabricated)" % tag,
           n["ocr"] == 0, "rows=%d" % n["ocr"])
    arm.ok("E %s: marker table empty" % tag, n["marker"] == 0,
           "rows=%d" % n["marker"])
    bad = conn.execute("SELECT COUNT(*) FROM segment WHERE n_visual<>0 OR n_ocr<>0"
                       ).fetchone()[0]
    arm.ok("E %s: every segment row says n_visual=0 and n_ocr=0" % tag,
           bad == 0, "violations=%d" % bad)
    bad = conn.execute("SELECT COUNT(*) FROM segment WHERE n_speech<>1"
                       ).fetchone()[0]
    arm.ok("E %s: every segment row says n_speech=1" % tag, bad == 0,
           "violations=%d" % bad)


# ---------------------------------------------------------------------------
# window census -- our own cadence, not the 60 s house governor
# ---------------------------------------------------------------------------

class WindowCensus(threading.Thread):
    """Samples the visibility of every window owned by the tracked pid tree.

    A 60 s house census CANNOT prove the absence of a window: it can only
    prove presence.  Whatever proves absence has to sample fast enough to
    catch the run.  25 ms it is, and the tracked set is seeded with every
    pid the gate itself spawns (the driver, the ASR worker, the helper).
    """

    def __init__(self, interval=0.025):
        threading.Thread.__init__(self, name="clipasr-window-census",
                                  daemon=True)
        self.interval = interval
        self.tracked = set([int(os.getpid())])
        self.samples = 0
        self.hits = []
        self.stopped = threading.Event()
        self._cb = None
        self._u32 = None

    def track(self, pids):
        for p in pids or []:
            if p:
                self.tracked.add(int(p))

    def _ensure(self):
        if self._cb is not None:
            return
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        tracked = self.tracked
        hits = self.hits

        def cb(hwnd, lparam):
            if not u32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if int(pid.value) not in tracked:
                return True
            n = int(u32.GetWindowTextLengthW(hwnd))
            buf = ctypes.create_unicode_buffer(max(n + 1, 2))
            u32.GetWindowTextW(hwnd, buf, n + 1)
            hits.append((int(pid.value), int(hwnd), buf.value))
            return True

        self._u32 = u32
        self._cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                      ctypes.c_void_p)(cb)

    def run(self):
        self._ensure()
        while not self.stopped.is_set():
            try:
                self._u32.EnumWindows(self._cb, None)
            except Exception:
                pass
            self.samples += 1
            time.sleep(self.interval)

    def stop(self):
        self.stopped.set()
        try:
            self.join(timeout=5.0)
        except RuntimeError:
            pass

    def report(self, arm):
        distinct = sorted(set(h[0] for h in self.hits))
        arm.ok("W no visible console window in %d samples at %.0f ms"
               % (self.samples, self.interval * 1000.0),
               len(self.hits) == 0,
               "hits=%d distinct_pids=%d" % (len(self.hits), len(distinct)))
        for h in self.hits[:10]:
            arm.note("HIT pid=%d hwnd=%d title=%s" % h)
        arm.note("census tracked pids: " + ",".join(str(p) for p in sorted(self.tracked)))
        return {"samples": self.samples, "hits": self.hits, "distinct": distinct}


def pid_alive(pid):
    """True iff that process has NOT exited.  Measured against os.getpid() of
    the gate itself and against a living child, 2026-10-09: WaitForSingleObject
    returns WAIT_TIMEOUT 258 for a process that is still running and
    WAIT_OBJECT_0 0 for one that exited.  259 is STILL_ACTIVE, an EXIT CODE
    value the wait API NEVER returns, so the old `== 259` reported every live
    process as dead and D2c measured False for a sleeping worker."""
    if not pid:
        return False
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x10000000, False, int(pid))   # SYNCHRONIZE
    if not h:
        return False
    try:
        return int(k.WaitForSingleObject(h, 0)) == 258       # WAIT_TIMEOUT
    finally:
        k.CloseHandle(h)


def ffmpeg_tool():
    try:
        return C._tool("ffmpeg")
    except C.ClipToAsrError:
        try:
            return C._tool("ffmpeg.exe")
        except C.ClipToAsrError as e:
            raise Refuse("ffmpeg not found: " + str(e))


def build_video_only_clip(path):
    """A clip with ONE trak, vide only -- the exact shape mp4_writer.cpp emits."""
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_tool()
    cmd = [str(ff), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
           "-t", "2", "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)]
    env = dict(os.environ)
    env["PATH"] = str(Path(ff).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                        errors="replace", env=env,
                        creationflags=C.CREATE_NO_WINDOW)
    if r.returncode != 0 or not path.is_file():
        raise Refuse("could not build the video-only fixture: " + (r.stderr or "")[-300:])
    return path


# ---------------------------------------------------------------------------
# the stub ASR workers used by arm D (dead) and arm D2 (stalled)
# ---------------------------------------------------------------------------

STALL_HELPER_NAME = "_clipasr_stall_child.py"
DEAD_CMD_TMPL = "%s -c %s"   # BOTH %s must be quote_arg()d: shlex.split splits
#   the space in and eats the backslashes of C:/Program Files/Python311/python.exe

def stall_script_path(work):
    return work / STALL_HELPER_NAME


def make_stall_helper(work):
    """Write the stall child and RETURN its path.

    It returned None until 2026-10-09: arm_d2 bound that None, so the stall
    command it built read '"python.exe" "None" <wav>', the worker exited rc=2
    in milliseconds, no pidfile was ever written, and the arm measured its own
    broken argv as a hung worker (D2c pid=None, D2f asr-worker-failed).  A
    helper whose path the caller cannot see is not a helper.
    """
    p = stall_script_path(work)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "import os, sys, time\n"
        "from pathlib import Path\n"
        "pid = Path(sys.argv[0] + '.pid')\n"
        "pid.write_text(str(os.getpid()), encoding='utf-8')\n"
        "sys.stdout.write('CLIPASR-STALL-CHILD pid=' + str(os.getpid()))\n"
        "sys.stdout.flush()\n"
        "time.sleep(600.0)\n",
        encoding="utf-8")
    return p


def run_cli_json(clip, db, work, asr_cmd=None, timeout_s=None, phase="all",
                 out_name="verdict.json"):
    """Run the real CLI in-process and return (rc, verdict-dict).

    In-process on purpose: the worker it spawns is what needs the no-window
    flag, and C.main hands that to it.  stdout is captured so the arm can
    assert the CLI actually emits the loud status, not just the code.
    """
    out = work / out_name
    cmd = [phase, "--clip", str(clip), "--db", str(db), "--tmpdir", str(work),
           "--json", "--out", str(out)]
    if asr_cmd:
        cmd += ["--asr-cmd", asr_cmd]
    if timeout_s is not None:
        cmd += ["--asr-timeout-s", str(timeout_s)]
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = C.main(cmd)
    finally:
        sys.stdout = old
    verdict = None
    for line in buf.getvalue().splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            verdict = json.loads(line)
        except Exception:
            pass
    return rc, verdict


# ---------------------------------------------------------------------------
# ARMS
# ---------------------------------------------------------------------------

def arm_a(clip, work, census):
    arm = Arm("ARM-A")
    db = work / "index.db"
    conn = store.connect(db, create=True)
    r = C.asr_index(conn, clip=clip, tmpdir=str(work))
    asr = r.get("asr") or {}
    census.track([asr.get("pid")])
    arm.ok("A1 pipeline status is ok", r["status"] == "ok", str(r["status"]))
    arm.ok("A2 it says the channel is speech", r.get("channel") == "speech",
           str(r.get("channel")))
    vcols = [x[1] for x in conn.execute("PRAGMA table_info(video)")]
    vrows = conn.execute("SELECT * FROM video").fetchall()
    arm.ok("A3 exactly one video row for the clip", len(vrows) == 1,
           "rows=%d" % len(vrows))
    key = hashlib.sha256(clip.read_bytes()).hexdigest()
    v = dict(zip(vcols, vrows[0])) if vrows else {}
    arm.ok("A4 video.content_key is the whole-file sha256 of the clip",
           v.get("content_key") == key, "%s" % str(v.get("content_key"))[:20])
    arm.ok("A5 the video row is NOT keyed by path (path is an attribute, not the key)",
           v.get("path") != v.get("content_key")
           and str(v.get("path", "")).endswith(clip.name),
           str(v.get("path"))[-40:])
    arm.ok("A6 the video row carries the clip duration in ms",
           int(v.get("duration_ms") or 0) == 15000,
           "duration_ms=%s" % v.get("duration_ms"))
    arm.ok("A7 the video row carries the clip geometry (video.w/video.h)",
           (int(v.get("w") or 0), int(v.get("h") or 0)) == (1280, 720),
           "w=%s h=%s" % (v.get("w"), v.get("h")))

    q = ("SELECT t.seg_id, t.start_ms, s.start_ms, s.end_ms, t.text, t.producer,"
         " t.model_sha256, s.n_speech, s.n_visual, s.n_ocr, s.state"
         " FROM transcript t JOIN segment s ON s.seg_id = t.seg_id"
         " ORDER BY t.rowid")
    tr = conn.execute(q).fetchall()
    arm.ok("A8 at least one speech row exists (>=1)", len(tr) >= 1,
           "n=%d" % len(tr))
    arm.ok("A9 every speech row carries a non-empty transcript line",
           tr and all(len((x[4] or "").strip()) > 0 for x in tr),
           "chars=%s" % str([len(x[4] or "") for x in tr]))
    arm.ok("A10 every speech row carries start_ms and end_ms",
           all(x[1] is not None and x[2] is not None and x[3] is not None
               and int(x[3]) > int(x[2]) for x in tr),
           "spans=%s" % str([[x[2], x[3]] for x in tr]))
    arm.ok("A11 provenance channel is literally 'speech' on every row",
           all(x[5] == C.SPEECH_CHANNEL for x in tr),
           "producers=%s" % str(sorted(set(x[5] for x in tr))))
    arm.ok("A12 every speech row names the model that produced it",
           all(x[6] for x in tr), "model=%s" % str(tr[0][6])[:16] if tr else "-")
    arm.ok("A13 every segment row counts exactly one speech row",
           all((x[7], x[8], x[9]) == (1, 0, 0) for x in tr),
           "n=(%s)" % str([[x[7], x[8], x[9]] for x in tr]))
    arm.ok("A14 every segment row is in state 'light'",
           all(x[10] == "light" for x in tr),
           "states=%s" % str(sorted(set(x[10] for x in tr))))

    # the speech rows must be FINDABLE, which is the point of the channel
    for tok in ("ponte", "interditada", "moradores", "radio"):
        n = conn.execute("SELECT COUNT(*) FROM text_fts WHERE text_fts MATCH ?",
                         (tok,)).fetchone()[0]
        arm.ok("A15 fts5 finds '%s' in the speech rows" % tok, n == 1, "n=%d" % n)
    j = conn.execute("SELECT f.rowid, f.source, f.seg_id, s.start_ms, s.end_ms"
                     " FROM text_fts f JOIN segment s ON s.seg_id = f.rowid"
                     " WHERE text_fts MATCH 'ponte'").fetchall()
    arm.ok("A16 an fts hit joins to the segment and names its channel",
           len(j) == 1 and j[0][1] == "transcript",
           "row=%s" % (str([list(x) for x in j])[:120],))
    arm.ok("A17 the fts rowid IS the seg_id (transcript rowid contract)",
           len(j) == 1 and int(j[0][0]) == int(j[0][2]),
           "rowid=%s seg_id=%s" % (j[0][0], j[0][2]) if j else "-")

    check_no_fabrication(arm, conn, "A")
    arm.note("measured clip minutes=%.3f speech_rows=%d"
             % (float(v.get("duration_ms") or 0) / 60000.0, len(tr)))
    arm.note("asr rss_peak_mb=%s infer_s=%s audio_s=%s rtfx_steady=%s"
             % (asr.get("rss_peak_mb"), asr.get("infer_s"), asr.get("audio_s"),
                asr.get("rtfx_steady")))
    conn.close()
    return arm, r, db


# ---------------------------------------------------------------------------
# ARM C / C2 -- idempotence, proven with counts and hashes only
# ---------------------------------------------------------------------------

def arm_c(clip, work, census, db):
    arm = Arm("ARM-C")
    conn = store.connect(db)
    before = {}
    for t in TABLES:
        before[t] = table_hash(conn, t)
    fp_before = C.fingerprint(conn)
    sids_before = [r[0] for r in
                   conn.execute("SELECT seg_id FROM segment ORDER BY rowid")]
    r2 = C.asr_index(conn, clip=clip, tmpdir=str(work))
    census.track([(r2.get("asr") or {}).get("pid")])
    for t in TABLES:
        now = table_hash(conn, t)
        arm.ok("C1 %-9s row count UNCHANGED by the second run" % t,
               now["rows"] == before[t]["rows"],
               "%d -> %d" % (before[t]["rows"], now["rows"]))
        arm.ok("C2 %-9s row sha256 UNCHANGED by the second run" % t,
               now["sha256"] == before[t]["sha256"],
               "%s -> %s" % (before[t]["sha256"][:12], now["sha256"][:12]))
    sids_after = [r[0] for r in
                  conn.execute("SELECT seg_id FROM segment ORDER BY rowid")]
    arm.ok("C3 the same seg_id list, same order", sids_before == sids_after,
           "%d rows" % len(sids_after))
    d = C.fingerprint_diff(fp_before, C.fingerprint(conn))
    arm.ok("C4 fingerprint_diff() reports an EMPTY change set", d == {},
           json.dumps(d)[:120])
    arm.ok("C5 the second run performs ZERO inserts (row_actions == kept)",
           r2.get("row_actions") == {"kept": len(sids_before)},
           json.dumps(r2.get("row_actions")))
    arm.ok("C6 the second run is still status ok, not a conflict",
           r2["status"] == "ok")
    arm.ok("C7 the second run reports the SAME content_key identity",
           r2["video"]["content_key"] == hashlib.sha256(clip.read_bytes()).hexdigest(),
           str(r2["video"]["content_key"])[:16])
    arm.note("measured: %d speech rows survive a repeat of the SAME clip, "
             "0 inserts" % len(sids_after))
    check_no_fabrication(arm, conn, "C")
    conn.close()
    return arm


def arm_c2(clip, work, census, db):
    arm = Arm("ARM-C2")
    copy = work / "same-clip-other-name.mp4"
    shutil.copyfile(clip, copy)
    key = hashlib.sha256(clip.read_bytes()).hexdigest()
    conn = store.connect(db)
    n_before = counts(conn)
    r = C.asr_index(conn, clip=copy, tmpdir=str(work))
    census.track([(r.get("asr") or {}).get("pid")])
    n_after = counts(conn)
    arm.ok("C2a a DIFFERENT path holding the SAME bytes still yields ONE video row",
           n_after["video"] == 1 and n_before["video"] == 1,
           "%d -> %d" % (n_before["video"], n_after["video"]))
    arm.ok("C2b the identity column content_key did not move",
           r["video"]["content_key"] == key, str(r["video"]["content_key"])[:16])
    arm.ok("C2c no second set of speech rows (row_actions == kept)",
           r.get("row_actions") == {"kept": n_before["transcript"]},
           json.dumps(r.get("row_actions")))
    v = conn.execute("SELECT content_key, path FROM video LIMIT 1").fetchone()
    arm.ok("C2d the row is found BY content, not by path (path is just data)",
           v[0] == key, "path now names " + Path(v[1]).name)
    arm.note("measured after the second name: path=%s content_key unchanged"
             % str(v[1])[-46:])
    check_no_fabrication(arm, conn, "C2")
    conn.close()
    return arm


# ---------------------------------------------------------------------------
# ARM D1 -- the ASR worker dies: loud status, clip keeps its video row
# ---------------------------------------------------------------------------

def quote_arg(s):
    """ONE shlex.split token: python on this box lives under Program Files.

    run_asr builds the worker argv with shlex.split(asr_cmd), and a bare
    C:/Program Files/Python311/python.exe BOTH splits at the space and loses
    its backslashes to POSIX escaping (measured: shlex.split turned it into
    ['C:Program', 'FilesPython311python.exe']).  Double quotes survive shlex
    and as_posix() removes the backslashes that would be eaten.
    """
    return chr(34) + str(Path(s).as_posix()).replace(chr(34), "") + chr(34)


def arm_d1(clip, work, census):
    arm = Arm("ARM-D1")
    db = work / "index.db"
    dead = "%s -c %s" % (quote_arg(sys.executable),
                        quote_arg("import sys;sys.exit(7)"))
    rc, verdict = run_cli_json(clip, db, work, asr_cmd=dead, out_name="d1.json")
    arm.ok("D1a the CLI exits 3 (the ASR arm of the exit contract)", rc == 3,
           "rc=%s" % rc)
    arm.ok("D1b the status word is specific, not a generic 'failed'",
           verdict is not None and verdict.get("status") == "asr-worker-failed",
           str(verdict and verdict.get("status")))
    msg = str((verdict or {}).get("message") or "")
    arm.ok("D1c the message names the worker AND its exit code",
           msg.startswith("asr-worker-failed") and "7" in msg, msg[:90])
    st = (verdict or {}).get("index_state") or {}
    arm.ok("D1d the verdict itself counts the EMPTY speech channel",
           st.get("speech_segments") == 0 and st.get("transcript_rows") == 0,
           json.dumps(st))
    arm.ok("D1e ...and the video row the clip owns anyway",
           st.get("video_rows") == 1, json.dumps(st))
    conn = store.connect(db)
    n = counts(conn)
    arm.ok("D1f in the DB itself video=1 segment=0 transcript=0 fts=0",
           (n["video"], n["segment"], n["transcript"], n["text_fts"]) == (1, 0, 0, 0),
           json.dumps({k: n[k] for k in ("video", "segment", "transcript",
                                         "text_fts")}))
    check_no_fabrication(arm, conn, "D1")
    conn.close()
    return arm


# ---------------------------------------------------------------------------
# ARM D2 -- the ASR worker STALLS: capture must not wait for it
# ---------------------------------------------------------------------------

def build_d2_driver(clip, db, work, stall):
    """A SECOND PROCESS runs the CLI while this one polls the index.

    The second connection is the point: a pipeline that held a write
    transaction across the ASR call would make the video row unreadable until
    the worker finished.  Reading it on another connection while the worker is
    demonstrably still alive is the only honest form of the claim that the
    capture path is never blocked.
    """
    src = (
        "import sys, json\n"
        "sys.path.insert(0, %r)\n"
        "from pipeline import clip_to_asr as C\n"
        "rc = C.main(['all', '--clip', %r, '--db', %r, '--tmpdir', %r, '--json',\n"
        "            '--asr-cmd', %r, '--asr-timeout-s', '4.0'])\n"
        "print('DRIVER-RC ' + str(rc))\n"
    ) % (str(_SRC), str(clip), str(db), str(work), str(stall))
    return src


def arm_d2(clip, work, census):
    arm = Arm("ARM-D2")
    db = work / "index.db"
    helper = make_stall_helper(work)
    pidfile = Path(str(helper) + ".pid")
    if pidfile.exists():
        pidfile.unlink()
    stall = "%s %s" % (quote_arg(sys.executable), quote_arg(str(helper)))
    src = build_d2_driver(clip, db, work, stall)
    proc = subprocess.Popen([sys.executable, "-c", src], cwd=str(_SRC),
                            env=C._child_env(C.INTRA_OP, C.INTER_OP),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=C.CREATE_NO_WINDOW)
    census.track([proc.pid])
    t0 = time.perf_counter()
    seen = None
    stalled_pid = None
    stalled_alive = False
    polls = 0
    while time.perf_counter() - t0 < 60.0:
        polls += 1
        if seen is None:
            try:
                c2 = store.connect(db)
                row = c2.execute("SELECT content_key FROM video LIMIT 1").fetchone()
                c2.close()
                if row is not None:
                    seen = time.perf_counter() - t0
            except Exception:
                pass
        if seen is not None:
            try:
                stalled_pid = int(pidfile.read_text(encoding="utf-8").strip())
            except Exception:
                stalled_pid = None
            census.track([stalled_pid])
            if stalled_pid is not None and pid_alive(stalled_pid):
                stalled_alive = True
                break
            if proc.poll() is not None:
                break
        time.sleep(0.02)
    try:
        out = proc.communicate(timeout=120)[0]
    except Exception:
        proc.kill()
        raise Refuse("the arm D2 driver never exited")
    arm.note("measured: %d polls at 20 ms; video row visible at t=%.3f; "
             "stalled worker pid=%s" % (polls, seen if seen is not None else -1.0,
                                        stalled_pid))
    arm.ok("D2a the video row is readable on a SECOND connection while the ASR "
           "worker is stalled", seen is not None, "t=%s" % (seen,))
    arm.ok("D2b ...within 2 s (the stall budget is 600 s, the timeout 4 s)",
           seen is not None and seen < 2.0, "t=%.3fs" % (seen or -1.0))
    arm.ok("D2c the stalled worker was provably ALIVE at that instant",
           stalled_alive, "pid=%s" % stalled_pid)
    rc = -1
    for line in out.splitlines():
        if line.startswith("DRIVER-RC "):
            rc = int(line.split()[-1])
    arm.ok("D2d the driver ran the CLI to the end", rc != -1, "rc=%d" % rc)
    arm.ok("D2e the CLI exits 3 (asr-worker-timeout)", rc == 3, "rc=%d" % rc)
    verdict = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                verdict = json.loads(line)
            except Exception:
                pass
    arm.ok("D2f the status word is asr-worker-timeout, not a hang",
           verdict is not None and verdict.get("status") == "asr-worker-timeout",
           str(verdict and verdict.get("status")))
    st = (verdict or {}).get("index_state") or {}
    arm.ok("D2g the verdict reports the EMPTY speech channel and the video row",
           st.get("speech_segments") == 0 and st.get("transcript_rows") == 0
           and st.get("video_rows") == 1, json.dumps(st))
    arm.ok("D2h the stall is the measurement: the worker was killed at the "
           "timeout", "asr-worker-timeout" in json.dumps(verdict or {}), "")
    conn = store.connect(db)
    n = counts(conn)
    arm.ok("D2i in the DB video=1 segment=0 transcript=0 fts=0",
           (n["video"], n["segment"], n["transcript"], n["text_fts"]) == (1, 0, 0, 0),
           json.dumps({k: n[k] for k in ("video", "segment", "transcript",
                                         "text_fts")}))
    check_no_fabrication(arm, conn, "D2")
    conn.close()
    return arm


# ---------------------------------------------------------------------------
# ARM SHAPE -- what the fixture stands in for, read off the capture source
# ---------------------------------------------------------------------------

def arm_shape():
    arm = Arm("ARM-SHAPE")
    cpp = _SRC / "capture" / "mp4_writer.cpp"
    arm.ok("S1 the capture source is present to be read", cpp.is_file(), str(cpp))
    txt = cpp.read_text(encoding="utf-8", errors="replace")
    arm.ok("S2 it builds exactly ONE trak box",
           txt.count("Box trak(") == 1, "Box trak( x %d" % txt.count("Box trak("))
    arm.ok("S3 that trak's handler type is literally vide",
           'hdlr.b.insert(hdlr.b.end(), (const uint8_t*)"vide"' in txt, "")
    arm.ok("S4 there is NO soun handler in the capture source",
           txt.count('(const uint8_t*)"soun"') == 0, "count=%d"
           % txt.count('(const uint8_t*)"soun"'))
    arm.ok("S5 therefore a clip captured TODAY has no audio trak to extract",
           txt.count('(const uint8_t*)"soun"') == 0
           and txt.count("Box trak(") == 1, "fixture MP4 stands in for lane C")
    arm.note("the fixture MP4 was BUILT by ffmpeg with an aac audio track: "
             "it is the clip shape lane C will mux, NOT a capture clip")
    return arm


# ---------------------------------------------------------------------------
# ARM V -- a video-only clip is REFUSED, never given a fake speech row
# ---------------------------------------------------------------------------

def arm_v(clip, work, census):
    arm = Arm("ARM-V")
    vo = build_video_only_clip(VIDEOONLY_CLIP)
    probe = C.ffprobe_clip(vo)
    has_audio = bool(probe.get("has_audio"))
    arm.ok("V1 the video-only fixture really has no audio stream",
           not has_audio, json.dumps({k: probe.get(k) for k in
                                      ("n_streams", "n_audio", "has_audio")}))
    arm.ok("V2 ...and it is the same mp4/moov family as a real capture clip",
           str(probe.get("codec", "")).startswith("h264"),
           "codec=%s" % probe.get("codec"))
    db = work / "index.db"
    rc, verdict = run_cli_json(vo, db, work, out_name="v.json")
    arm.ok("V3 the CLI refuses it with a status word, not a silent pass",
           verdict is not None and verdict.get("status") in
           ("wav-extract-failed", "wav-contract-refused"),
           str(verdict and verdict.get("status")))
    arm.ok("V4 ...and the exit code is one of the refusal codes (2 or 3)",
           rc in (2, 3), "rc=%s" % rc)
    conn = store.connect(db)
    n = counts(conn)
    arm.ok("V5 NOT one speech row is fabricated on it",
           (n["segment"], n["transcript"], n["text_fts"]) == (0, 0, 0),
           json.dumps({k: n[k] for k in ("segment", "transcript", "text_fts")}))
    arm.ok("V6 the clip still gets its video row (the mux failure is not its "
           "fault)", n["video"] == 1, "video=%d" % n["video"])
    check_no_fabrication(arm, conn, "V")
    conn.close()
    return arm


# ---------------------------------------------------------------------------
# ARM X -- a CHANGED transcript for a minted seg_id is refused, never written
# ---------------------------------------------------------------------------

def fresh_db(work):
    """Point at an EMPTY index: the gate never clears work/ itself, so a run that
    crashes (or is interrupted) would otherwise leave its rows behind and arm the
    NEXT run with a stale index -- which is exactly how ARM-NEG originally failed:
    its control run INSERTed rows the earlier crashed run had already written, so
    the copy's clean INSERT became an UPDATE and died on the FTS5 delete trigger
    BEFORE the arm could measure anything.  Self-inflicted stale state is not a
    subject.  Wal/shm go with the db or SQLite re-opens the old frames."""
    db = work / "index.db"
    for sfx in ("", "-wal", "-shm"):
        q = Path(str(db) + sfx)
        if q.is_file():
            q.unlink()
    return db

def arm_x(clip, work, census):
    arm = Arm("ARM-X")
    db = fresh_db(work)
    key = hashlib.sha256(clip.read_bytes()).hexdigest()
    sid0 = C.seg_id_for(key, 0)
    stale = "a line left by a different, older pipeline"
    stale_id = "stale-model-id"
    # The stale row must sit on a segment row that REALLY exists: transcript
    # carries an FK on segment(seg_id) (src/index/schema.sql:86) and the FK fires
    # before anything else can -- measured as sqlite3.IntegrityError: FOREIGN KEY
    # constraint failed when this arm seeded a bare seg_id, which made the arm
    # crash instead of measuring the refusal.  So the seed builds the video row
    # with the SHIPPED phase-1 code and the segment row with the SAME values arm A
    # measured for start 0 (0..8000 ms, n_speech=1, state=light), and the checks
    # below then compare the whole index before and after the failed run.
    conn = store.connect(db, create=True)
    vid = C.index_clip(conn, clip=clip, content_key=key)["video_id"]
    store.upsert_segment(conn, video_id=vid, seg_id=sid0, start_ms=0, end_ms=8000,
                         n_visual=0, n_speech=1, n_ocr=0, state="light")
    store.upsert_transcript(conn, seg_id=sid0, text=stale, text_norm=stale,
                            start_ms=0, producer="speech",
                            model_sha256=stale_id)
    conn.commit()
    fp_seed = C.fingerprint(conn)
    n_seed = counts(conn)
    conn.close()
    rc, verdict = run_cli_json(clip, db, work, out_name="x.json")
    arm.ok("X1 a CHANGED transcript for an already-minted seg_id is REFUSED",
           verdict is not None and verdict.get("status") == "speech-row-conflict",
           str(verdict and verdict.get("status")))
    arm.ok("X2 the exit code is 2 (bad state, not an ASR failure)", rc == 2,
           "rc=%s" % rc)
    msg = str((verdict or {}).get("message") or "")
    arm.ok("X3 the refusal names the seg_id and the conflicting fields",
           str(sid0) in msg, msg[:120])
    conn = store.connect(db)
    row = conn.execute("SELECT text, model_sha256 FROM transcript WHERE seg_id=?",
                       (sid0,)).fetchone()
    arm.ok("X4 the stale line is NOT silently overwritten",
           row is not None and row[0] == stale and row[1] == stale_id,
           "text=%s" % (row[0][:40] if row else None))
    n = counts(conn)
    arm.ok("X5 the failed run changed NOTHING -- no new row, no moved byte",
           n == n_seed and C.fingerprint(conn) == fp_seed,
           json.dumps({k: n[k] for k in ("video", "segment", "transcript")}))
    conn.close()
    return arm


# ---------------------------------------------------------------------------
# the RED arm -- the shipped preflight REMOVED, on a copy, tails the copy
# ---------------------------------------------------------------------------

def build_negation():
    """A byte-copy of the module with ONE thing removed: write_speech_row."""
    real_file = _HERE / "clip_to_asr.py"
    real = real_file.read_text(encoding="utf-8")
    anchor = ("        action = write_speech_row(conn, seg_id=sid, text=text, start_ms=start_ms,\n"
              "                                  producer=SPEECH_CHANNEL, model_sha256=model_id)\n")
    if anchor not in real:
        raise Refuse("the negation anchor is not in the shipped module: the "
                     "preflight it removes has moved")
    broken = real.replace(anchor,
                          "        store.upsert_transcript(conn, seg_id=sid, text=text,\n"
                          "                             text_norm=text, start_ms=start_ms,\n"
                          "                             producer=SPEECH_CHANNEL,\n"
                          "                             model_sha256=model_id)\n"
                          "        action = 'inserted'\n")
    dst = _HERE / NEG_FILE
    dst.write_text(broken, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("clipasr_negation", str(dst))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["clipasr_negation"] = mod
    return dst, mod


def arm_neg(clip, work, census):
    arm = Arm("ARM-NEG")
    dst = None
    try:
        dst, M = build_negation()
        db = fresh_db(work)
        conn = store.connect(db, create=True)
        r1 = M.asr_index(conn, clip=clip, tmpdir=str(work))
        census.track([(r1.get("asr") or {}).get("pid")])
        arm.ok("NEG1 control: the copy is NOT merely broken -- its first run "
               "indexes the clip", r1["status"] == "ok" and r1["n_speech_rows"] >= 1,
               "status=%s rows=%d" % (r1["status"], r1["n_speech_rows"]))
        n1 = counts(conn)
        arm.ok("NEG2 control: the first run really wrote the video row and the "
               "speech rows", n1["video"] == 1 and n1["transcript"] >= 1,
               json.dumps({k: n1[k] for k in ("video", "segment", "transcript",
                                              "text_fts")}))
        fp_before = C.fingerprint(conn)
        err = None
        try:
            M.asr_index(conn, clip=clip, tmpdir=str(work))
        except Exception as e:                       # the RED must land here
            err = e
        arm.ok("NEG3 the RED fires: the SECOND run raises", err is not None,
               type(err).__name__ if err else "no exception")
        arm.ok("NEG4 it is the FTS5 'delete' trigger failure, not anything else",
               isinstance(err, sqlite3.OperationalError)
               and "SQL logic error" in str(err), repr(str(err))[:150])
        arm.ok("NEG5 the index is byte-identical after the failed second run "
               "(nothing half-written)", C.fingerprint(conn) == fp_before, "")
        r3 = C.asr_index(conn, clip=clip, tmpdir=str(work))
        census.track([(r3.get("asr") or {}).get("pid")])
        arm.ok("NEG6 the REAL module succeeds on that very database -- the fix "
               "is the preflight, not luck",
               r3["status"] == "ok" and r3.get("row_actions") ==
               {"kept": n1["transcript"]}, json.dumps(r3.get("row_actions")))
        conn.close()
    finally:
        if dst is not None and dst.exists():
            try:
                dst.unlink()
            except OSError:
                pass
    return arm


# ---------------------------------------------------------------------------
# the measurement report
# ---------------------------------------------------------------------------

def measure_report(db, rss_peak_mb):
    conn = store.connect(db)
    v = conn.execute("SELECT duration_ms FROM video LIMIT 1").fetchone()
    fp = C.fingerprint(conn)
    sb = sum(fp.get(t, {}).get("bytes", 0)
             for t in ("segment", "transcript", "text_fts"))
    st = store.store_bytes(conn)
    conn.close()
    dur_s = float(v[0]) / 1000.0 if v else 0.0
    mins = dur_s / 60.0
    return {
        "clip_seconds": dur_s,
        "speech_rows_fingerprint_bytes": sb,
        "speech_row_bytes_per_clip_minute": (sb / mins) if mins else 0.0,
        "db_file_bytes": st["file_bytes"], "db_file_mib": st["file_mib"],
        "db_page_size": st["page_size"],
        "db_mib_per_clip_minute": (float(st["file_mib"]) / mins) if mins else 0.0,
        "asr_rss_peak_mb_max": rss_peak_mb,
        "speech_rows": fp.get("transcript", {}).get("rows", 0),
    }


def print_report(label, rep):
    print("CLIPASR-REPORT " + label + " " + json.dumps(rep, sort_keys=True))
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def parse_args(argv):
    ap = argparse.ArgumentParser(description="CLIP-TO-ASR gate, both colours "
                                             "in one command")
    ap.add_argument("--neg-arm", action="store_true",
                    help="run ONLY the red arm (the preflight removed on a copy)")
    ap.add_argument("--skip-neg", action="store_true",
                    help="run only the green arm")
    ap.add_argument("--clip", default=str(DEFAULT_CLIP))
    ap.add_argument("--work", default=str(DEFAULT_WORK))
    ap.add_argument("--census-ms", type=float, default=25.0)
    ap.add_argument("--only", default="",
                    help="comma-separated arm keys: shape,a,c,c2,d1,d2,v,x")
    return ap.parse_args(argv)


# the green arms, with their real dependencies.  --only keeps the dependency
# honest instead of silently skipping an arm that needs another one's rows.
GREEN_ARMS = ("shape", "a", "c", "c2", "d1", "d2", "v", "x")
DEPENDS = {"c": ("a",), "c2": ("a",)}


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    clip = Path(args.clip).resolve()
    if not clip.is_file():
        raise Refuse("the clip fixture is missing: " + str(clip))
    if not C._default_model_dir().is_dir():
        raise Refuse("the ASR model directory is missing: "
                     + str(C._default_model_dir()))
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    only = frozenset(x.strip() for x in args.only.split(",") if x.strip())
    for k in list(only):
        only |= frozenset(DEPENDS.get(k, ()))
    want = lambda k: (not only) or (k in only)      # noqa: E731
    for k in only:
        if k not in GREEN_ARMS and k != "neg":
            raise Refuse("unknown arm key: " + k)

    print("CLIPASR-GATE subject " + str(clip))
    print("CLIPASR-GATE work " + str(work) + " model "
          + str(C._default_model_dir()))
    print("CLIPASR-GATE colours green=real module  red=negation copy "
          "(write_speech_row removed)")
    print("CLIPASR-GATE FIXTURE ffmpeg-built with an aac track: it stands in "
          "for the muxed clip lane C will produce, NOT a capture clip")
    sys.stdout.flush()

    census = WindowCensus(max(args.census_ms, 5.0) / 1000.0)
    census.start()
    arms = []
    errors = []
    rss = 0.0
    n_speech = 0
    negarm = None
    try:
        if args.neg_arm:
            negarm = arm_neg(clip, work / "neg", census)
        else:
            dba = work / "a" / "index.db"
            if want("shape"):
                arms.append(arm_shape())
            if want("a"):
                arm, res, _db = arm_a(clip, work / "a", census)
                arms.append(arm)
                asr = res.get("asr") or {}
                rss = max(rss, float(asr.get("rss_peak_mb") or 0.0))
                n_speech = int(res.get("n_speech_rows") or 0)
            if want("c"):
                arms.append(arm_c(clip, work / "a", census, dba))
            if want("c2"):
                arms.append(arm_c2(clip, work / "a", census, dba))
            if want("d1"):
                arms.append(arm_d1(clip, work / "d1", census))
            if want("d2"):
                arms.append(arm_d2(clip, work / "d2", census))
            if want("v"):
                arms.append(arm_v(clip, work / "v", census))
            if want("x"):
                arms.append(arm_x(clip, work / "x", census))
            for a in arms:
                print("CLIPASR-GATE %-10s %s checks=%d failed=%d"
                      % (a.name, "GREEN" if a.green else "RED", a.checks,
                         a.failed))
            sys.stdout.flush()
            if not only and (work / "a" / "index.db").is_file():
                print_report("asr", measure_report(dba, rss))
            if not args.skip_neg:
                negarm = arm_neg(clip, work / "neg", census)
    except Refuse as e:
        errors.append(str(e))
    finally:
        census.stop()

    print_report("census", {"samples": census.samples,
                            "visible_hits": len(census.hits),
                            "distinct_pids": sorted(set(h[0] for h
                                                        in census.hits))})
    w = Arm("ARM-W")
    census.report(w)
    arms.append(w)

    total = sum(a.checks for a in arms)
    failed = sum(a.failed for a in arms)
    if errors:
        for e in errors:
            print("CLIPASR-GATE REFUSED " + e)
        return 2
    green = failed == 0
    print("CLIPASR-GATE %s arms=%d checks=%d failed=%d"
          % ("PASS" if green else "FAIL", len(arms), total, failed))
    neg_ok = None
    if negarm is not None:
        neg_ok = negarm.green
        print("CLIPASR-GATE-NEG %s checks=%d failed=%d"
              % ("PASS" if neg_ok else "FAIL", negarm.checks, negarm.failed))
    if args.neg_arm:
        print("CLIPASR-FINAL %s" % ("PASS" if neg_ok else "FAIL"))
        return 0 if neg_ok else 1
    print("CLIPASR-FINAL %s" % ("PASS" if (green and neg_ok) else "FAIL"))
    return 0 if (green and neg_ok) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refuse as e:
        sys.stderr.write("CLIPASR-GATE REFUSED " + str(e) + "\n")
        sys.exit(2)
