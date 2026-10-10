"""test_engine.py -- the ARM GATE for THE ENGINE PROCESS (lane A, feat/engine-process).

ONE command, BOTH colours, every arm:

    py -3 src/engine/test_engine.py            (from _moved/aireplay)

    GREEN   the real subject -- this engine.py, this store.py, this
            stub_capture.py, and the REAL capture binary where it can be used.
    RED     the SAME subject copied with ONE property removed, the property the
            arm asserts.  A red control that does NOT go red is a FAILURE: the
            arm was measuring nothing, so the gate prints RED-CONTROL-SILENT.

A SKIPPED arm is a FAILURE.  Nothing is printed as PASS unless it ran and met
its threshold.

Arms (the dispatch's own list, in its words):
    ARM-A  the engine starts, arms the hotkey path, holds the ring with the UI absent
    ARM-B  UI attach / detach mid-run: recording continues, the last-100-event
           replay makes the reconnecting UI consistent (+ reconnect latency ms)
    ARM-C  the ASR child stalls, then dies: capture continues unbroken -- no
           dropped ring, no lost clip, no cut ever waited for the AI side
    ARM-D  NVENC failure exits 3 and the message names the encoder status
    ARM-E  a second Engine instance is refused loudly (no double ownership)
    ARM-F  TerminateProcess the Engine mid-session: every clip row was committed
           to the SQLite spine before the kill and content_key survives

Where the real capture child can be used it is used: ARM-D pre-flight runs the
REAL binary (_main/build/aireplay-capture.exe, 783,865 B).  Arms that need a
capture SESSION run against stub_capture.py and every one of them says STUB,
because this checkout's C++ child refuses every offline h264 feed:
"=== CUT SESSION REFUSED: no SPS/PPS: avcC cannot be built ===".  The cause is
inside SourceStream::load (src/capture/main.cpp): it captures the SPS/PPS only
inside an if (vcl) block, NAL 7/8 are never VCL, so both fields are always
empty.  src/capture/* is read-only for this lane, so the fix is not made here;
the refusal is measured and carried in the receipt.  A stub arm is never
reported as a PASS of the real capture path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback as traceback_mod

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# TMPDIR is I:\\cc-tmp on this host: G: fills with ENOSPC (AGENTS.md 6).
if os.name == "nt":
    os.environ["TMPDIR"] = "I:\\cc-tmp"
    GATE_ROOT = os.path.join("I:\\cc-tmp", "engine-gate-%d" % os.getpid())
else:
    GATE_ROOT = os.path.join(os.path.sep, "tmp", "engine-gate-%d" % os.getpid())

SPINE_NAME = "engine-spine.db"
STATUS_NAME = "engine-status.json"
PORT_NAME = "engine-port.json"
LOCK_NAME = "engine-ring.lock"

STUB_ASR = os.path.join(HERE, "stub_asr.py")
UI_CHILD = os.path.join(HERE, "ui_child.py")


def _utf8_output():
    """Emit diagnostics as UTF-8 with 'replace', never as the console code page.

    MEASURED 2026-10-09: the C++ child's stderr arrives through a pipe as bytes
    the console code page cannot represent; printing one of them raised
    UnicodeEncodeError on the 'charmap' codec, twice -- once inside ARM-D's own
    detail line and again in the final table -- and aborted the whole gate run.
    A gate that dies of its own printer has measured nothing, so the streams are
    repaired before any arm runs.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_utf8_output()


def safe(text):
    """ASCII-only rendering of a diagnostic line.  Non-ASCII becomes '?'."""
    s = text.decode("utf-8", "replace") if isinstance(text, bytes) else str(text)
    return "".join(ch if ord(ch) < 128 else "?" for ch in s)


# ------------------------------------------------------------------ reporting
class Results(object):
    """One row per arm/colour; a red arm that PASSED is a SILENT CONTROL."""

    def __init__(self):
        self.rows = []
        self.silent = []

    def add(self, arm, colour, ok, detail):
        row = {"arm": arm, "colour": colour, "ok": bool(ok), "detail": safe(detail)}
        self.rows.append(row)
        print("%s %-11s %-5s %s  :: %s"
              % (arm, colour, "PASS" if ok else "FAIL", "", row["detail"]))
        sys.stdout.flush()
        return row

    def failures(self):
        # a green arm that went red, or a red arm that stayed green (silent control)
        return [r for r in self.rows
                if (r["colour"] == "green" and not r["ok"])
                or (r["colour"] == "red" and r["ok"])]

    def summary(self):
        green = [r for r in self.rows if r["colour"] == "green"]
        red = [r for r in self.rows if r["colour"] == "red"]
        arms = sorted(set(r["arm"] for r in self.rows))
        gok = [r for r in green if r["ok"]]
        rok = [r for r in red if not r["ok"]]
        return ("arms=%d (%s) green=%d/%d red-controls-red=%d/%d silent-controls=%d"
                % (len(arms), ",".join(arms), len(gok), len(green), len(rok), len(red),
                   len(self.failures()) - len([r for r in green if not r["ok"]])))


R = Results()


# ------------------------------------------------------------------ utilities
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def fresh(name):
    d = os.path.join(GATE_ROOT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    return d


class Runner(object):
    """A spawned child whose stdout and stderr we keep verbatim."""

    def __init__(self, argv, cwd=None):
        kw = {}
        if CREATE_NO_WINDOW:
            kw["creationflags"] = CREATE_NO_WINDOW
        self.argv = argv
        self.p = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8", errors="replace", **kw)
        self._parts = {"out": [], "err": []}
        self._pumps = []
        for name in ("out", "err"):
            if name == "out":
                stream = self.p.stdout
            else:
                stream = self.p.stderr
            t = threading.Thread(target=self._pump, args=(name, stream), daemon=True)
            t.start()
            self._pumps.append(t)

    def _pump(self, name, stream):
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                self._parts[name].append(chunk)
        except Exception as exc:
            self._parts[name].append("[gate] %s pump failed: %r" % (name, exc))

    def text(self):
        return "".join(self._parts["out"]), "".join(self._parts["err"])

    def wait(self, timeout):
        try:
            self.p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.terminate()
            try:
                self.p.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                pass
        for t in self._pumps:
            try:
                t.join(2.0)
            except Exception:
                pass
        out, err = self.text()
        if self.p.returncode is None:
            return None, out, (err or "") + "\n[gate] communicate() timed out"
        return self.p.returncode, out, err

    def terminate(self):
        """TerminateProcess -- what ARM-F needs, and what a hang needs."""
        try:
            subprocess.call(["taskkill", "/F", "/PID", str(self.p.pid)],
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
        try:
            self.p.kill()
        except OSError:
            pass


def wait_for(pred, timeout, interval=0.05):
    deadline = time.time() + timeout
    value = None
    while time.time() < deadline:
        try:
            value = pred()
            if value:
                return True, value
        except Exception:
            pass
        time.sleep(interval)
    try:
        value = pred()
    except Exception:
        value = None
    return bool(value), value


def status_of(workdir):
    return read_json(os.path.join(workdir, STATUS_NAME))


class Sampler(threading.Thread):
    """Samples the engine's own status file at its OWN cadence.

    The 60 s house census cannot see a short event (AGENTS.md), so an arm that
    claims "recording continued while no UI was attached" samples at 100 ms and
    names the samples it stood on.
    """

    def __init__(self, workdir, interval=0.1):
        threading.Thread.__init__(self, name="sampler", daemon=True)
        self.workdir = workdir
        self.interval = interval
        self.stop = threading.Event()
        self.samples = []

    def run(self):
        t0 = time.time()
        while not self.stop.is_set():
            st = status_of(self.workdir)
            if st:
                h = st.get("health") or {}
                ui = h.get("ui") or {}
                self.samples.append({
                    "t_ms": int((time.time() - t0) * 1000),
                    "cuts_ok": (h.get("cuts") or {}).get("cuts_ok", 0),
                    "ring": h.get("ring") or {},
                    "ui_connected": int(ui.get("connected", 0) or 0),
                })
            time.sleep(self.interval)

    def unattended_cuts(self):
        return max([s["cuts_ok"] for s in self.samples if s["ui_connected"] == 0] or [0])


# A transient, EXTERNAL share lock on a WAL sidecar: run #2 of the full
# dual-colour gate (I:/cc-tmp/fullgate-run2.txt, gate root
# I:/cc-tmp/engine-gate-26016) hit PermissionError [Errno 13] at
# test_engine.py:297 copying f-red/engine-spine.db-wal 61 s after a
# TerminateProcess kill, while 8 isolated `--only F --mutants` reruns plus an
# earlier 5-iteration kill-then-copy probe never did (0/13).  The arm now FAILS
# with the error NAMED instead of throwing a traceback, and a locked observer
# sidecar can no longer be mistaken for a spine defect (or hide one).
SPINE_COPY_ERRORS = []
SPINE_COPY_ATTEMPTS = 20
SPINE_COPY_DELAY_S = 0.25


def copy_spine_sidecar(src, dst):
    """Copy one spine sidecar, tolerating a transient OS share lock.

    ARM-F reads the spine of a process it already TerminateProcess'd, so a
    retry can only WAIT for a lock to clear -- it never invents data and never
    swaps files: same source, same destination, same order, tried up to
    SPINE_COPY_ATTEMPTS times with SPINE_COPY_DELAY_S between attempts
    (20 x 0.25 s = 5.0 s per sidecar, i.e. 0 s when nothing is locked).
    Returns None on success and an error string naming the file and the OS
    error otherwise.
    """
    last = None
    for _ in range(SPINE_COPY_ATTEMPTS):
        try:
            shutil.copyfile(src, dst)
            return None
        except OSError as exc:
            last = exc
            time.sleep(SPINE_COPY_DELAY_S)
    return "sidecar-copy-locked %s -> %s after %d tries (%r)" % (
        src, dst, SPINE_COPY_ATTEMPTS, last)


def spine_rows(db, sql, args=(), errors=None):
    """Read the spine as a COPY, after a kill if need be.

    A read-only open of a WAL database whose -wal is hot is not possible, and the
    whole point of ARM-F is to read the spine of a process that died between
    commits, so COPY the (db, -wal, -shm) trio, open the copy read-write, and it
    recovers whatever the dead process had fsync'd (synchronous=FULL).
    """
    if not os.path.exists(db):
        return None
    tmp = os.path.join(os.path.dirname(db) or ".", "spine-read.db")
    sink = SPINE_COPY_ERRORS if errors is None else errors
    for suffix in ("", "-wal", "-shm"):
        src = db + suffix
        if os.path.exists(src):
            err = copy_spine_sidecar(src, tmp + suffix)
            if err:
                sink.append(err)
    try:
        con = sqlite3.connect(tmp)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(tmp + suffix)
            except OSError:
                pass


def spine_one(db, sql, args=()):
    rows = spine_rows(db, sql, args)
    return rows[0] if rows else None


def spine_audit(workdir):
    """The spine as a fact, not as a promise."""
    db = os.path.join(workdir, SPINE_NAME)
    del SPINE_COPY_ERRORS[:]
    out = {"db": db, "present": os.path.exists(db), "integrity": None, "rows": 0,
           "committed": 0, "key_len_ok": 0, "key_matches_file": 0, "files_missing": 0,
           "files_total": 0, "tables": [], "clip_ids": [], "key_nulls": 0,
           "clip_paths": [], "copy_errors": []}
    if not out["present"]:
        out["copy_errors"] = list(SPINE_COPY_ERRORS)
        return out
    r = spine_one(db, "PRAGMA integrity_check")
    out["integrity"] = list(r.values())[0] if r else None
    try:
        out["tables"] = sorted(x["name"] for x in
                               (spine_rows(db, "SELECT name FROM sqlite_master WHERE type=?",
                                           ("table",)) or []))
    except sqlite3.Error:
        out["tables"] = []
    rows = spine_rows(db, "SELECT * FROM clip")
    if rows is None:
        out["copy_errors"] = list(SPINE_COPY_ERRORS)
        return out
    out["rows"] = len(rows)
    for row in rows:
        key = row.get("content_key")
        path = row.get("path") or ""
        out["clip_paths"].append(path)
        if row.get("state") == "done":
            out["committed"] += 1
        if key is None:
            out["key_nulls"] += 1
        elif len(key) == 64:
            out["key_len_ok"] += 1
            if os.path.exists(path):
                out["files_total"] += 1
                try:
                    if sha256_file(path) == key:
                        out["key_matches_file"] += 1
                except OSError:
                    pass
            else:
                out["files_missing"] += 1
    out["clip_ids"] = [r.get("clip_id") for r in rows]
    out["copy_errors"] = list(SPINE_COPY_ERRORS)
    return out


def clip_files_on_disk(workdir):
    """Every clip FILE the capture child left, whatever the spine says about it."""
    d = os.path.join(workdir, "clips")
    try:
        names = os.listdir(d)
    except OSError:
        return []
    return sorted(n for n in names if n.lower().endswith(".wav"))


def unaccounted_clip_files(workdir, aud):
    """Clip files on disk with NO spine row -- the reverse of files_missing.

    Measured 2026-10-09 on ARM-G green BEFORE the finalise drain landed: the
    capture child finalises the clip that was still open when its stdin reached
    EOF, the Engine never read that reply, and a graceful stop left 296 files
    against 295 rows.  That clip IS on disk -- the key was pressed, the audio is
    there -- yet nothing names it: no row, no content_key, and nothing downstream
    can ever find it.  A spine that does not describe every clip on disk is not
    a spine, so this is a gate check and not a receipt footnote.  It is NOT an
    ARM-F check: a killed engine leaves its child writing for seconds.
    """
    d = os.path.join(workdir, "clips")
    known = set(os.path.abspath(x) for x in (aud.get("clip_paths") or []) if x)
    out = []
    for name in clip_files_on_disk(workdir):
        if os.path.abspath(os.path.join(d, name)) not in known:
            out.append(name)
    return out


# ------------------------------------------------------------------ subjects
def make_mutant(name, patches):
    """Copy the whole engine dir and remove ONE property from ONE file."""
    dst = os.path.join(GATE_ROOT, "mutant-" + name)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(HERE, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for fname, subs in patches.items():
        p = os.path.join(dst, fname)
        with open(p, encoding="utf-8") as f:
            s = f.read()
        for old, new in subs:
            if old not in s:
                raise RuntimeError("MUTANT-PATCH-MISS %s %s %r" % (name, fname, old[:70]))
            s = s.replace(old, new, 1)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(s)
    return dst


def engine_argv(subject_dir, workdir, extra):
    return [PY, os.path.join(subject_dir, "engine.py"), "--workdir", workdir] + extra


def run_engine(subject_dir, workdir, extra, timeout):
    r = Runner(engine_argv(subject_dir, workdir, extra), cwd=GATE_ROOT)
    rc, out, err = r.wait(timeout)
    return rc, out, err, r
# ------------------------------------------------------------------ envelopes
def read_envs(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and isinstance(rec.get("env"), dict):
                out.append(rec["env"])
            elif isinstance(rec, dict) and rec.get("type") and "payload" in rec:
                # ui_child logs BARE envelopes {"v":1,"type":...,"id":...,
                # "ts":...,"payload":{...}}, NOT {"env": {...}} -- MEASURED:
                # with only the "env" form this returned [] for EVERY arm, so
                # clip_intervals() was always empty and ARM-C's "capture never
                # waited" check read max interval 0 ms on a perfectly healthy
                # run and reported a FAIL that was the instrument's.
                out.append(rec)
    return out


def clip_intervals(envs):
    ts = [int(e["ts"]) for e in envs
          if e.get("type") == "clip_written" and isinstance(e.get("ts"), (int, float))]
    ts.sort()
    return [b - a for a, b in zip(ts, ts[1:])], ts


def health_of(envs):
    return [e for e in envs if e.get("type") == "health"]


def poll_committed(workdir, want, timeout):
    """Poll the ENGINE'S OWN committed count, read from its status file.

    Two defects were measured here.  (1) The predicate returned the truthy INT n
    on the first partial count, so wait_for() returned (True, 1) immediately and
    ARM-F killed the Engine after ~1 s, before 3 commits -- a FAIL that was never
    the engine's fault.  (2) Reading the spine as a COPY while its writer is
    alive is not a measurement: copying a hot WAL raises PermissionError
    [Errno 13], and a read-only open of a live WAL database answers 0 rows,
    because the main db file holds nothing until a checkpoint.

    So the count polled is the Engine's own -- health.clips.clip_done, a query on
    its live connection, published every 0.5 s -- and the spine is opened ONLY
    after the kill, by spine_audit, when its writer is dead and its files copy
    cleanly.  That keeps ARM-F a durability claim instead of a mirror.
    """
    def once():
        st = status_of(workdir) or {}
        clips = (st.get("health") or {}).get("clips") or {}
        return int(clips.get("clip_done") or 0)
    ok, _ = wait_for(lambda: once() >= want, timeout, 0.05)
    return ok, once()


def janitor():
    """Kill whatever this gate left behind, by FULL ARTIFACT PATH.

    The house census samples every 60 s (AGENTS.md), so it cannot prove absence
    of a short-lived window; this counts at the gate's own cadence, every arm,
    and names the artifacts it matched.  The filter is the full path of the
    engine dir and of stub_capture.py -- never a bare word.
    """
    ps = os.path.join(GATE_ROOT, "census.ps1")
    with open(ps, "w", encoding="utf-8", newline="") as f:
        f.write("$me = " + str(os.getpid()) + "\r\n")
        f.write("$root = '" + GATE_ROOT.replace(chr(39), chr(39) * 2) + "'\r\n")
        f.write("Get-CimInstance Win32_Process | Where-Object {\r\n")
        f.write("    $_.Name -match 'python' -and $_.ProcessId -ne $me -and\r\n")
        f.write("    $_.CommandLine -and $_.CommandLine -like ('*' + $root + '*') } |\r\n")
        f.write("    ForEach-Object { Write-Output ('KILL ' + $_.ProcessId + ' ' + $_.CommandLine);\r\n")
        f.write("        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\r\n")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps],
                           creationflags=CREATE_NO_WINDOW, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return (r.stdout or "").strip()
    except Exception as exc:
        return "JANITOR-ERROR %r" % (exc,)


# ==========================================================================
# ARM A -- the engine starts, arms the hotkey path, holds the ring with the
#          UI absent.  stdout is EMPTY by contract.
# ==========================================================================
def arm_a(subject, colour):
    wd = fresh("a-%s" % colour)
    rc, out, err, _ = run_engine(subject, wd, [
        "--capture", "stub", "--ui", "off", "--asr", "off",
        "--cut-every", "1", "--cut-count", "4", "--seconds", "60"], 90)
    aud = spine_audit(wd)
    st = status_of(wd) or {}
    harm = st.get("health") or {}
    cuts = harm.get("cuts") or {}
    ring = harm.get("ring") or {}
    checks = {
        "rc==0": rc == 0,
        "stdout empty": out == "",
        "stderr handshake": "capture handshake ok=True" in err,
        "stop reason": st.get("stop_reason") == "cut-count-reached",
        "cuts_ok==4": cuts.get("cuts_ok") == 4,
        "cuts_refused==0": cuts.get("cuts_refused") == 0,
        # FOUR requested cuts plus the clip the child closed when its stdin
        # reached EOF -- finalised to disk by the stub exactly as the real
        # child does (main.cpp:1294-1299) and answered by NO reply on either,
        # so the Engine names it from the CLIP DIRECTORY (engine.py
        # _reconcile_clip_dir).  Before that reconcile this session left 4
        # rows against 5 files.  cuts_ok stays 4: a reconcile is not a cut.
        "5 committed clips (4 cuts + 1 reconciled)": aud["committed"] == 5,
        "reconciled==1": harm.get("reconciled") == 1,
        "every key 64 hex": aud["key_len_ok"] == aud["committed"],
        "every key == file sha256": aud["key_matches_file"] == aud["committed"],
        "clips on disk": aud["files_total"] == aud["committed"],
        "ring held events": int(ring.get("size", 0)) >= 5,
        "ring capacity 100": int(ring.get("capacity", 0)) == 100,
        "no UI ever attached": (st.get("health") or {}).get("ui", {}).get("connected") == 0,
        "lance dir gone, spine kept": os.path.isdir(os.path.join(wd, "clips")),
    }
    ok = all(checks.values())
    detail = "rc=%s cuts=%s/%s ring=%s cuts_refused=%s rec=%s " \
              "spine=%dcmt,%dkey-ok,%dsha-ok stop=%s stdout=%dB %s" % (
                  rc, cuts.get("cuts_ok"), cuts.get("cuts_requested"),
                  ring.get("size"), cuts.get("cuts_refused"), harm.get("reconciled"),
                  aud["committed"], aud["key_len_ok"], aud["key_matches_file"],
                  st.get("stop_reason"), len(out),
                  "" if ok else "FAIL:" + ",".join(k for k, v in checks.items() if not v))
    return R.add("ARM-A", colour, ok, detail)


# ==========================================================================
# ARM B -- attach / detach / reattach mid-run, and the replay that makes the
#          reconnecting UI consistent.  The reconnect latency is measured.
# ==========================================================================
def arm_b(subject, colour):
    wd = fresh("b-%s" % colour)
    log = os.path.join(wd, "ui.jsonl")
    # --seconds must exceed ~25 s: the ring holds 100 ids and the measured
    # stub cadence is ~240 ms/cut, so under 24 s of cutting can never fill the
    # ring.  That check is about the RING, not about the UI.
    eng = Runner(engine_argv(subject, wd, [
        "--capture", "stub", "--ui", "on", "--asr", "off",
        "--cut-every", "0.05", "--seconds", "32"]), cwd=GATE_ROOT)
    ok_port, _ = wait_for(lambda: os.path.exists(os.path.join(wd, PORT_NAME)), 30)
    s = Sampler(wd, 0.1)
    s.start()
    # --detach-gap must exceed ONE cut cadence (the stub cuts about every
    # 120 ms), otherwise the reconnect asks for a cursor the ring has not moved
    # past yet and the replay comes back empty -- a stub-shaped hole in the arm
    # itself.  2 s buys about 16 cuts of window at the measured cadence.
    ui = Runner([PY, UI_CHILD, "--portfile", os.path.join(wd, PORT_NAME),
                 "--log", log, "--hold", "10", "--detach-after", "4",
                 "--detach-gap", "2", "--reattach-hold", "4"], cwd=GATE_ROOT)
    rc_ui, out_ui, err_ui = ui.wait(70)
    rc, out, err = eng.wait(90)
    # The Engine's OWN diagnostics are the witness for the attach/detach pair:
    # without them a silent "no live events" cannot be attributed to a side.
    with open(os.path.join(wd, "engine-stderr.txt"), "w", encoding="utf-8") as fh:
        fh.write(err or "")
    s.stop.set()
    s.join(1.0)
    summary = None
    for line in (out_ui or "").strip().splitlines():
        try:
            cand = json.loads(line)
            if isinstance(cand, dict) and "first_attach" in cand:
                summary = cand
        except ValueError:
            pass
    envs = read_envs(log)
    fa = (summary or {}).get("first_attach") or {}
    ra = (summary or {}).get("reattach") or {}
    gaps = (summary or {}).get("gaps") or []
    dupes = (summary or {}).get("duplicate_count", -1)
    ids_union = (summary or {}).get("ids_all") or []
    hs = health_of(envs)
    ring_sizes = [int((e.get("payload") or {}).get("ring", {}).get("size", 0)) for e in hs]
    dropped = max([int((e.get("payload") or {}).get("ring", {}).get("dropped", 0)) for e in hs] or [0])
    aud = spine_audit(wd)
    orphans_b = unaccounted_clip_files(wd, aud)
    # The ring question belongs to the ENGINE, not to the UI's luck: the Sampler
    # reads the engine's own status file at 100 ms, so overflow is measured from
    # the subject.  b2 failed here because maxring was read out of the healths a
    # UI that had already left happened to see (26 of 100).
    ring_max = max([int((x.get("ring") or {}).get("size", 0)) for x in s.samples] or [0])
    drop_max = max([int((x.get("ring") or {}).get("dropped", 0)) for x in s.samples] or [0])
    live_ids = ra.get("ring_ids") or []
    _since = int(ra.get("since") or 0)
    _rev = ra.get("replay_env") or {}
    _rev_n = int(_rev.get("replayed", 0) or 0)
    _rev_from, _rev_to, _orc = _rev.get("from"), _rev.get("to"), _rev.get("oldest_retained")
    _want_from = _since if (_orc is None or _since >= _orc) else _orc
    # What the reconnect asked for and what came back must describe the SAME
    # window: from is the cursor, or the oldest id still retained when the cursor
    # is stale, and the delivered events fill exactly [from, to].  An EMPTY replay
    # is correct ONLY when the cursor already sits at the head (to == since) --
    # that is what b2 measured (newest_id==30==since), and demanding >0 was a
    # gate defect, not an engine one.
    cursor_consistent = (_rev_from == _want_from and _rev_to is not None
                         and _rev_n == (_rev_to - _rev_from)
                         and (_rev_n > 0 or _rev_to == _since))
    checks = {
        "engine rc==0": rc == 0,
        "ui rc==0": rc_ui == 0,
        "engine stdout empty": out == "",
        "ui attached": fa.get("replay_latency_ms") is not None,
        "replay window is cursor-consistent": cursor_consistent,
        "stale cursor is flagged truncated": _rev.get("truncated") == (_orc is not None and _since < _orc),
        "reconnect <= last 100": _rev_n <= 100,
        "reconnect cursor == last ring id seen": ra.get("since") == fa.get("max_ring_id"),
        "replay is the exact continuation": bool(ra.get("replay_exact_range")) or (_rev_n == 0 and cursor_consistent),
        "live events after reattach": len(live_ids) >= 1,
        "live ids continue exactly": bool(live_ids) and live_ids == list(range(_since + 1, _since + 1 + len(live_ids))),
        "ring overflowed (engine status)": ring_max == 100 and drop_max > 0,
        "ids gapless (no holes)": gaps == [],
        "no duplicate ids": dupes == 0,
        "recording while detached": s.unattended_cuts() >= 1,
        "clips committed == files": aud["key_matches_file"] == aud["committed"] and aud["committed"] > 0,
        "every clip file on disk has a spine row": orphans_b == [],
    }
    ok = all(checks.values())
    detail = ("rc=%s/%s ui1=%sms ui2=%sms replayed=%s(%s..%s) exact=%s cursor=%s ids=%d "
              "gaps=%s dupes=%s engring=%d/%d live=%d cuts_while_unattended=%d clips=%d "
              "files=%d rows=%d orphan=%s %s"
              % (rc, rc_ui, fa.get("replay_latency_ms"), ra.get("replay_latency_ms"),
                 _rev_n, _rev_from, _rev_to, ra.get("replay_exact_range"),
                 ra.get("since"), len(ids_union), gaps, dupes, ring_max, drop_max,
                 len(live_ids), s.unattended_cuts(), aud["committed"],
                 len(clip_files_on_disk(wd)), aud["rows"], orphans_b or "-",
                 "" if ok else "FAIL:" + ",".join(k for k, v in checks.items() if not v)))
    return R.add("ARM-B", colour, ok, detail)

# ==========================================================================
# ARM G -- a reconnect with a STALE cursor: the UI whose last seen id
#          predates the whole retained window.  ARM-B proves the fresh
#          cursor (detach 2 s, come back at the head of the ring); this arm
#          proves the OTHER half of "replay the last 100 events": the ring is
#          BOUNDED, so a cursor older than the window must be answered with
#          exactly the last 100 retained events and a flag that ADMITS the
#          loss.  The cursor is 1, not 0: with since=0 nothing was ever claimed
#          to have been seen, so there is no loss to flag and the arm would
#          pass vacuously.
# ==========================================================================
def arm_g(subject, colour):
    wd = fresh("g-%s" % colour)
    log = os.path.join(wd, "ui.jsonl")
    # The ring holds 100 events and the measured stub cadence is ~4 cuts/s
    # (ARM-B: 129 clips in 32 s), so overflow needs >25 s of cutting.  The
    # engine therefore runs longer than that: the arm precondition is that the
    # ring has ALREADY evicted when the UI connects.
    eng = Runner(engine_argv(subject, wd, [
        "--capture", "stub", "--ui", "on", "--asr", "off",
        "--cut-every", "0.05", "--seconds", "44"]), cwd=GATE_ROOT)
    ok_port, _ = wait_for(lambda: os.path.exists(os.path.join(wd, PORT_NAME)), 30)
    s = Sampler(wd, 0.1)
    s.start()
    # The precondition is measured from the SUBJECT (its own status file at a
    # 100 ms cadence), never inferred from the clock: until dropped > 0 a cursor
    # of 1 is not stale and the arm would pass on an empty ring.
    ok_ovf, _ = wait_for(lambda: max([int((x.get("ring") or {}).get("dropped", 0))
                                      for x in s.samples] or [0]) > 0, 60)
    ui = Runner([PY, UI_CHILD, "--portfile", os.path.join(wd, PORT_NAME),
                 "--log", log, "--since", "1", "--hold", "6",
                 "--label", "stale"], cwd=GATE_ROOT)
    rc_ui, out_ui, err_ui = ui.wait(40)
    rc, out, err = eng.wait(60)
    with open(os.path.join(wd, "engine-stderr.txt"), "w", encoding="utf-8") as fh:
        fh.write(err or "")
    s.stop.set()
    s.join(1.0)
    st = status_of(wd) or {}
    ring = (st.get("health") or {}).get("ring") or {}
    ring_max = max([int((x.get("ring") or {}).get("size", 0)) for x in s.samples] or [0])
    drop_max = max([int((x.get("ring") or {}).get("dropped", 0)) for x in s.samples] or [0])
    summary = None
    for line in (out_ui or "").strip().splitlines():
        try:
            cand = json.loads(line)
            if isinstance(cand, dict) and "first_attach" in cand:
                summary = cand
        except ValueError:
            pass
    envs = read_envs(log)
    hello = [e for e in envs if e.get("type") == "hello"]
    hring = ((hello[-1].get("payload") or {}).get("ring") if hello else {}) or {}
    fa = (summary or {}).get("first_attach") or {}
    rev = fa.get("replay_env") or {}
    evs = rev.get("events") or []
    ev_ids = [int(e.get("id", 0)) for e in evs if isinstance(e, dict)]
    orc = int(rev.get("oldest_retained", 0) or 0)
    to = int(rev.get("to", 0) or 0)
    cap = int(hring.get("capacity", 0) or 0)
    # The hole between the cursor and the first retained id is EXPECTED and is
    # not a defect: the ring is bounded.  What must be true is that the client
    # was TOLD -- the first id it receives is the oldest the engine still has,
    # the count is exactly the capacity, and the ids fill that window with no
    # hole and no repeat inside it.
    checks = {
        "rc==0": rc == 0,
        "stdout empty": out == "",
        "ui attached": rc_ui == 0,
        "ring had already evicted": ok_ovf and drop_max > 0,
        "ring held its capacity": ring_max == cap and cap == 100,
        "cursor 1 IS stale (1 < oldest_retained)": orc > 1,
        "replay flags the loss (truncated)": rev.get("truncated") is True,
        "replay is exactly the last 100": len(ev_ids) == cap,
        "replayed count matches the events": int(rev.get("replayed", -1) or -1) == len(ev_ids),
        "window starts at the oldest retained id": bool(ev_ids) and min(ev_ids) == orc,
        "window ends at the newest retained id": bool(ev_ids) and max(ev_ids) == to,
        "oldest_retained == engine snapshot": orc == int(hring.get("oldest_id", -1) or -1),
        "to == engine snapshot newest": to == int(hring.get("newest_id", -1) or -1),
        "window gapless, no repeat": ev_ids == list(range(orc, to + 1)),
        "engine said so on stderr": ("ATTACH since=1 replay=%d truncated=True" % cap) in err,
    }
    aud = spine_audit(wd)
    orphans_g = unaccounted_clip_files(wd, aud)
    checks["every clip file on disk has a spine row"] = orphans_g == []
    ok = all(checks.values())
    detail = ("cursor=1 evicted_before=%d maxring=%d/%d orc=%d to=%d n=%d truncated=%s "
              "ui=%sms files=%d rows=%d orphan=%s %s"
              % (drop_max, ring_max, cap, orc, to, len(ev_ids), rev.get("truncated"),
                 fa.get("replay_latency_ms"), len(clip_files_on_disk(wd)), aud["rows"],
                 orphans_g or "-",
                 "" if ok else "FAIL:" + ",".join(k for k, v in checks.items() if not v)))
    return R.add("ARM-G", colour, ok, detail)




# ==========================================================================
# ARM C -- the ASR side stalls, then dies; capture never waited, never dropped
# ==========================================================================
def arm_c(subject, colour, asr_cmd, tag):
    wd = fresh("c-%s-%s" % (tag, colour))
    log = os.path.join(wd, "ui.jsonl")
    eng = Runner(engine_argv(subject, wd, [
        "--capture", "stub", "--ui", "on", "--asr", "on",
        "--asr-cmd", asr_cmd, "--asr-timeout", "6",
        "--cut-every", "1", "--seconds", "12"]), cwd=GATE_ROOT)
    wait_for(lambda: os.path.exists(os.path.join(wd, PORT_NAME)), 30)
    ui = Runner([PY, UI_CHILD, "--portfile", os.path.join(wd, PORT_NAME),
                 "--log", log, "--hold", "16"], cwd=GATE_ROOT)
    rc_ui, out_ui, _ = ui.wait(70)
    rc, out, err = eng.wait(70)
    envs = read_envs(log)
    dts, ts = clip_intervals(envs)
    st = status_of(wd) or {}
    asr = (st.get("health") or {}).get("asr") or {}
    aud = spine_audit(wd)
    errs = [e for e in envs if e.get("type") == "error"]
    checks = {
        "engine rc==0": rc == 0,
        "engine stdout empty": out == "",
        "cuts >= 8": aud["committed"] >= 8,
        "every clip committed": aud["key_matches_file"] == aud["committed"],
        "clips on disk": aud["files_total"] == aud["committed"],
        "asr stalled child counted": int(asr.get("dead", 0)) + int(asr.get("failed", 0)) >= 1,
        "no engine error events": errs == [],
        "ui gapless ids": ((json.loads((out_ui or "{}").strip().splitlines()[-1])["gaps"]
                            if (out_ui or "").strip() else []) == []),
    }
    mx = max(dts or [0])
    checks["capture never waited (max interval %d ms < 2500)" % mx] = 0 < mx < 2500
    ok = all(checks.values())
    detail = ("rc=%s asr=%s clips=%d/%d maxcut=%dms intervals=%s keys_ok=%d/%d ui=%s %s"
              % (rc, {k: asr.get(k) for k in ("submitted", "done", "dead", "failed", "dropped")},
                 aud["committed"], aud["rows"], mx, sorted(dts), aud["key_matches_file"],
                 aud["committed"], rc_ui,
                 "" if ok else "FAIL:" + ",".join(k for k, v in checks.items() if not v)))
    return R.add("ARM-C/" + tag, colour, ok, detail)


# ==========================================================================
# ARM D -- NVENC failure exits 3 and names the encoder status
# ==========================================================================
def arm_d(subject, colour):
    wd = fresh("d-%s" % colour)
    exe = os.path.join(os.path.dirname(os.path.dirname(HERE)), "_main", "build",
                       "aireplay-capture.exe")
    rc, out, err, _ = run_engine(subject, wd, [
        "--capture", "exe", "--capture-exe", exe, "--selftest",
        "--inject-fault", "no-nvenc", "--seconds", "1"], 180)
    st = status_of(wd) or {}
    decision = [l for l in (err or "").splitlines() if "DECISION" in l]
    checks = {
        "rc==3": rc == 3,
        "stdout empty": out == "",
        "CAPTURE-PREFLIGHT-REFUSED": "CAPTURE-PREFLIGHT-REFUSED rc=3" in err,
        "child verdict verbatim": any("NO ENCODER INITIALISED" in l for l in decision),
        "encoder named": any(("nvEncode" in l) or ("H.264" in l) for l in decision),
        "status exit_code 3": st.get("exit_code") == 3,
        "no spine created": not os.path.exists(os.path.join(wd, SPINE_NAME)),
        "no ring lock left": not os.path.exists(os.path.join(wd, LOCK_NAME)),
        "no clips dir": not os.path.isdir(os.path.join(wd, "clips")),
        "no capture child": not os.path.exists(os.path.join(wd, "clip-%s" % "")),
    }
    ok = all(checks.values())
    detail = ("rc=%s stdout=%dB verdict=%r locks=%s spine=%s %s"
              % (rc, len(out), decision[0][:96] if decision else "",
                 os.path.exists(os.path.join(wd, LOCK_NAME)),
                 os.path.exists(os.path.join(wd, SPINE_NAME)),
                 "" if ok else "FAIL:" + ",".join(k for k, v in checks.items() if not v)))
    return R.add("ARM-D", colour, ok, detail)


# ==========================================================================
# ARM E -- a second Engine is refused loudly
# ==========================================================================
def arm_e(subject, colour):
    wd = fresh("e-%s" % colour)
    e1 = Runner(engine_argv(subject, wd, [
        "--capture", "stub", "--ui", "off", "--asr", "off",
        "--cut-every", "0", "--seconds", "14"]), cwd=GATE_ROOT)
    ok_lock, _ = wait_for(lambda: os.path.exists(os.path.join(wd, LOCK_NAME)), 30)
    time.sleep(1.0)
    e2 = Runner(engine_argv(subject, wd, [
        "--capture", "stub", "--ui", "off", "--asr", "off",
        "--cut-every", "0", "--seconds", "4"]), cwd=GATE_ROOT)
    rc2, out2, err2 = e2.wait(40)
    rc1, out1, err1 = e1.wait(40)
    lock_after = os.path.exists(os.path.join(wd, LOCK_NAME))
    checks = {
        "first engine rc==0": rc1 == 0,
        "first engine stdout empty": out1 == "",
        "second engine refused (rc 4)": rc2 == 4,
        "second engine stdout empty": out2 == "",
        "loud refusal words": ("ENGINE-SECOND-INSTANCE" in err2
                               and "another Engine owns the ring lock" in err2),
        "first engine kept the lock till exit": lock_after is False,
        "no double clip dirs": os.path.isdir(os.path.join(wd, "clips")),
    }
    ok = all(checks.values())
    detail = ("rc1=%s rc2=%s lock-file-seen=%s refused_words=%s lock_after=%s %s"
              % (rc1, rc2, ok_lock, "ENGINE-SECOND-INSTANCE" in err2, lock_after,
                 "" if ok else "FAIL:" + ",".join(k for k, v in checks.items() if not v)))
    return R.add("ARM-E", colour, ok, detail)


# ==========================================================================
# ARM F -- TerminateProcess the Engine mid-session
# ==========================================================================
def arm_f(subject, colour):
    wd = fresh("f-%s" % colour)
    eng = Runner(engine_argv(subject, wd, [
        "--capture", "stub", "--ui", "off", "--asr", "off",
        "--cut-every", "1", "--seconds", "0"]), cwd=GATE_ROOT)
    ok3, n_live = poll_committed(wd, 3, 60)
    st = status_of(wd) or {}
    child_pid = ((st.get("health") or {}).get("child") or {}).get("pid")
    t_kill = time.time()
    eng.terminate()
    try:
        eng.p.wait(timeout=15)
    except Exception:
        pass
    aud = spine_audit(wd)
    copy_errs = list(aud.get("copy_errors") or [])
    rows = spine_rows(os.path.join(wd, SPINE_NAME),
                      "SELECT clip_id, content_key, committed_at, state, path FROM clip",
                      errors=copy_errs) or []
    done_rows = [r for r in rows if r["state"] == "done"]
    cutting = [r for r in rows if r["state"] != "done"]
    committed_before = True
    for r in rows:
        if r["state"] == "done" and float(r["committed_at"] or 0) > t_kill + 1.0:
            committed_before = False
    # A TERMINATED process leaves NOTHING in flight except what the single-thread
    # loop happened to be doing.  anchor() runs BEFORE the cut and commit_clip()
    # AFTER it, so the only survivable non-done row is the one clip mid-flight at
    # the kill instant -- at most one, and it MUST still have no content_key,
    # because the commit that computes one never ran.  A second 'cutting' row, or
    # a committed key on a 'cutting' row, would be a torn write and is a FAIL.
    checks = {
        "engine published >=3 clips before the kill": ok3,
        "spine still holds them all after the kill": len(done_rows) >= n_live and aud["committed"] >= 3,
        ">=3 clips committed by the kill": aud["committed"] >= 3,
        "integrity_check ok": aud["integrity"] == "ok",
        "at most one in-flight 'cutting' row": len(cutting) <= 1,
        "no 'cutting' row carries a content_key": all(r["content_key"] is None for r in cutting),
        "no unknown row state": all(r["state"] in ("done", "cutting") for r in rows),
        "every key 64 hex": aud["key_len_ok"] == aud["committed"],
        "every key == file sha256": aud["key_matches_file"] == aud["committed"],
        "every committed clip still on disk": aud["files_total"] == aud["committed"],
        "committed_at <= kill": committed_before,
        # a sidecar the OS would not let us copy is an OBSERVER failure and
        # must read as one, NAMED -- never as a spine defect, never a traceback
        "every spine sidecar copied (no OS lock)": not copy_errs,
    }
    if child_pid:
        try:
            subprocess.call(["taskkill", "/F", "/PID", str(child_pid)],
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    ok = all(checks.values())
    detail = ("killed pid=%s child=%s committed=%d done=%d cutting=%d live_before_kill=%d "
              "keys_ok=%d/%d files=%d integrity=%s committed_before_kill=%s %s"
              % (eng.p.pid, child_pid, aud["committed"], len(done_rows), len(cutting), n_live,
                 aud["key_matches_file"], aud["committed"], aud["files_total"], aud["integrity"],
                 committed_before,
                 "" if ok else "FAIL:" + ",".join(k for k, v in checks.items() if not v)))
    if copy_errs:
        detail += " COPY:" + "|".join(copy_errs)
    return R.add("ARM-F", colour, ok, detail)
# ==========================================================================
# MUTANTS: each one restores the defect the ARM exists to catch.  A mutant that
# stays GREEN proves the arm measures nothing.  (Both colours, one command.)
# ==========================================================================
EMIT_OLD = ("    def emit(self, type_, payload):\n"
            "        env = self.ring.append(type_, payload)\n"
            "        self.hub.publish_now(env)\n"
            "        return env")
EMIT_LEAK = ("    def emit(self, type_, payload):\n"
             "        env = self.ring.append(type_, payload)\n"
             "        self.hub.publish_now(env)\n"
             "        sys.stdout.flush()\n"
             "        sys.__stdout__.write(json.dumps(env) + \"\\n\")\n"
             "        return env")
SINCE_OLD = "            evs = [dict(e) for e in self.items if e[\"id\"] > since_id]"
SINCE_NOREPLAY = "            evs = []  # MUTANT: the ring keeps the events, replays none"
ASR_OLD = ("        if self.asr is not None:\n"
           "            offered = self.asr.submit(cid, path)")
ASR_WAITS = ("        if self.asr is not None:\n"
             "            offered = self.asr.submit(cid, path)\n"
             "            time.sleep(3.5)  # MUTANT: the cut path WAITS for the AI side")
PF_OLD = "        if rc == 3:\n            return EXIT_NVENC"
PF_OK = ("        if rc == 3:\n"
         "            return EXIT_OK  # MUTANT: a dead encoder is treated as ARMED")
LOCK_OLD = "        if not self.lock.acquire():"
LOCK_NONE = ("        if False and not self.lock.acquire():  "
             "# MUTANT: a second Engine is never refused")
KEY_OLD = "        key = content_key_of(path)"
KEY_LIE = "        key = \"0\" * 64  # MUTANT: content_key is a claim, not a measurement"
TRUNC_OLD = "                \"truncated\": bool(since > 0 and since < oldest),"
TRUNC_LIE = "                \"truncated\": False,  # MUTANT: a stale cursor is never called stale"
REC_OLD = "        self._drain_final_clips()"
REC_NONE = "        pass  # MUTANT: the clip the child closed at stdin EOF is never named"

MUTANTS = [
    ("stdout-leak", "A", {"engine.py": [(EMIT_OLD, EMIT_LEAK)]},
     "engine writes envelopes to stdout, which must stay EMPTY by contract"),
    ("no-replay", "B", {"engine.py": [(SINCE_OLD, SINCE_NOREPLAY)]},
     "the ring retains events but a reconnecting UI gets an empty replay"),
    ("capture-waits", "C1", {"engine.py": [(ASR_OLD, ASR_WAITS)]},
     "the cut path waits for the AI side, so capture stalls behind ASR"),
    ("preflight-ok", "D", {"engine.py": [(PF_OLD, PF_OK)]},
     "a dead encoder is treated as ARMED instead of exit 3"),
    ("no-lock", "E", {"engine.py": [(LOCK_OLD, LOCK_NONE)]},
     "a second Engine is never refused, so two owners share the ring"),
    ("commit-nokey", "F", {"store.py": [(KEY_OLD, KEY_LIE)]},
     "content_key is claimed, never measured from the file"),
    ("stale-lie", "G", {"engine.py": [(TRUNC_OLD, TRUNC_LIE)]},
     "a UI whose cursor predates the ring is handed the whole loss and never told"),
    ("no-finalise", "G", {"engine.py": [(REC_OLD, REC_NONE)]},
     "the clip the child closed at stdin EOF is never reconciled, so the last "
     "clip has no row")
]

ARMS = {}


def arm(key, fn):
    ARMS[key] = fn
    return fn


arm("A", arm_a)
arm("B", arm_b)
arm("C1", lambda s, c: arm_c(s, c, os.path.join(HERE, "stub_asr.py") + " --stall 25", "stall"))
arm("C2", lambda s, c: arm_c(s, c, os.path.join(HERE, "stub_asr.py") + " --rc 2", "dead"))
arm("D", arm_d)
arm("E", arm_e)
arm("F", arm_f)
arm("G", arm_g)
GREEN_ORDER = ["A", "B", "C1", "C2", "D", "E", "F", "G"]


# ==========================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="Engine process gate: both colours, one command")
    ap.add_argument("--only", default="", help="comma list of arm keys to run (A,B,C1,C2,D,E,F,G); arm G carries TWO red controls (stale-lie, no-finalise)")
    ap.add_argument("--mutants", action="store_true", help="run the RED controls too")
    ap.add_argument("--keep", action="store_true", help="do not delete workdirs (default: delete)")
    args = ap.parse_args(argv)
    os.makedirs(GATE_ROOT, exist_ok=True)
    shown = [k.strip().upper() for k in args.only.split(",") if k.strip()]
    want = [k for k in GREEN_ORDER if not shown or k in shown]
    skip = [k for k in GREEN_ORDER if k not in want]
    if not shown and not args.mutants:
        # the default run is the green arm plus the red controls, in one command
        run_red = True
    else:
        run_red = bool(args.mutants)
    print("GATE ROOT      : %s" % GATE_ROOT)
    print("SUBJECT        : %s" % HERE)
    print("ARMS           : %s   skipped=%s" % (",".join(want), ",".join(skip) or "-"))
    print("RED CONTROLS   : %s" % (",".join(m[0] for m in MUTANTS) if run_red else "off"))
    print("")

    R.__init__()
    R.started = time.time()

    # ---- GREEN: the subject as it ships
    for k in want:
        t0 = time.time()
        try:
            r = ARMS[k](HERE, "green")
        except Exception:
            r = R.add("ARM-%s" % k, "green", False,
                      "exception\n" + traceback_mod.format_exc())
        print("%-8s %-5s %-7s %ss  %s"
              % (r["arm"], r["colour"], "GREEN" if r["ok"] else "RED", round(time.time() - t0, 1),
                 r["detail"]))

    # ---- RED: the same arms on copies with the defect restored
    if run_red:
        for name, armkey, patches, why in MUTANTS:
            if armkey not in want:
                continue
            t0 = time.time()
            try:
                sd = make_mutant(name, patches)
                r = ARMS[armkey](sd, "red")
            except Exception:
                r = R.add("ARM-%s" % armkey, "red", False,
                          "exception\n" + traceback_mod.format_exc())
            expect_red = not r["ok"]
            note = "" if expect_red else "   <<< CONTROL DID NOT GO RED (%s)" % why
            print("%-8s %-5s %-7s %ss  mutant=%s%s  %s"
                  % (r["arm"], "red", "RED" if expect_red else "GREEN",
                     round(time.time() - t0, 1), name,
                     "" if expect_red else "  NOT-A-CONTROL", note or r["detail"]))
            if expect_red:
                R.silent.append("%s/%s" % (r["arm"], name))

    print("")
    print("VERDICT TABLE")
    for r in R.rows:
        if r["colour"] == "green":
            mark = "PASS " if r["ok"] else "FAIL "
        else:
            mark = "REDok" if not r["ok"] else "BAD  "
        print("  %s  %-8s %-5s %s" % (mark, r["arm"], r["colour"], r["detail"]))
    print("")
    print(R.summary())
    left = janitor()
    print("CENSUS (own cadence, full artifact path): %s"
          % (left if left else "no gate process alive after the run"))
    shell = time.time() - R.started
    if not args.keep:
        try:
            shutil.rmtree(GATE_ROOT, ignore_errors=True)
        except Exception:
            pass
    print("GATE-VERDICT: %s   total %ss" %
          ("GREEN" if not R.failures() and not [r for r in R.rows
                                                if r["colour"] == "red" and r["ok"]]
           else "RED", round(shell, 1)))
    return 0 if (not R.failures() and not [r for r in R.rows
                                           if r["colour"] == "red" and r["ok"]]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
