
"""clip_to_asr -- the indexing HALF of build-order step 5.

A saved clip may already become SEARCHABLE over the speech channel, but two
invariants from the 8 laws are not negotiable while it happens:

  * THE CAPTURE PATH NEVER WAITS FOR THE MODEL.  An 815 MB int8 encoder is not
    something Alt+F10 may block on.  So this module is split in two phases and
    only the SMALL one is online:

    phase 1  index_clip()   hash -> ffprobe -> upsert_video.  no model, no ASR
                            process, no numpy, no onnxruntime import.
    phase 2  asr_index()    ffmpeg extract -> a SEPARATE worker process ->
                            minted seg_id -> upsert_segment/upsert_transcript.

    The Engine schedules phase 2; nothing here is ever called inline from the
    capture path.

  * THE RESULT IS IDEMPOTENT.  index.video.content_key is the identity (a
    whole-file SHA-256, UNIQUE), and store.upsert_video() is an ON CONFLICT.
    But index.segment has NO unique constraint on (video_id, start_ms) --
    receipt 24 sec. 7.1 measured that the chain is NOT idempotent past the
    video row, because store.upsert_segment(seg_id=None) plain-INSERTs a fresh
    row every call.  This module closes that from MY side, without touching
    src/index/: it MINTS seg_id = sha256 of (content_key, start_ms) reduced to
    a signed-63-bit integer and passes it in, which turns upsert_segment into
    an ON CONFLICT(seg_id) DO UPDATE no-op on the second run.  The mint is
    checked for a collision before it is used (refused loudly, never
    overwritten), because a collision would silently steal another row.

  * THE SPEECH CHANNEL SAYS IT IS THE SPEECH CHANNEL.  Every row this module
    writes carries n_speech=1 and n_visual=0 and n_ocr=0, and the transcript
    row carries producer='speech' -- the provenance channel, literal, because
    arm A demands a hit be able to say WHICH channel matched.

  * NO FABRICATED SENSORY DATA.  There are no visual or ocr embeddings in
    this lane and no model to build them, so zero such rows are written and
    the embedding table stays empty (arm E).  A REFUSAL beats a plausible row.

Exit status (the CLI contract, all of it loud and specific):

    0  speech rows are in the index (freshly written or idempotently refreshed)
    2  the input was bad: the clip does not exist, the wav contract was
       refused, or a minted seg_id collided
    3  the ASR worker FAILED: dead child, no done line, a stall past
       --asr-timeout-s, or a provider refusal.  The VIDEO ROW IS STILL THERE
       and the speech channel is EMPTY and says so (arm D).

The status word is the first token of every line this module prints, so a log
reader never has to guess which thing happened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve()
_SRC = _HERE.parents[1]
_REPO_ROOT = _HERE.parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from index import store  # noqa: E402  (sqlite only -- stays light on purpose)

# asr.constants VALUES are restated rather than imported: importing the asr
# package would pull onnxruntime into the phase-1 process, which must not.
DEFAULT_MAX_SEGMENT_S = 15.0      # asr.constants.MAX_SEGMENT_S
DEFAULT_SEGMENT_MODE = "silence"  # asr.constants.DEFAULT_SEGMENT_MODE
INTRA_OP = 4      # the recipe receipt 24 measured with
INTER_OP = 1      # the recipe receipt 24 measured with
SAMPLE_RATE = 16000
CREATE_NO_WINDOW = 0x08000000

# the provenance channel this lane owns.  arm A asserts this LITERAL.
SPEECH_CHANNEL = "speech"


class ClipToAsrError(RuntimeError):
    """A loud, specific refusal.  status is a machine-readable word."""

    def __init__(self, status, message, measured=None):
        super().__init__(status + ": " + message)
        self.status = status
        self.measured = measured or {}


# ---------------------------------------------------------------------------
# helpers that are meant to be re-used and unit-tested
# ---------------------------------------------------------------------------

_CHUNK = 1 << 20


def sha256_path(path):
    """Whole-file SHA-256 hex.  THIS is content_key.  Never key by path."""
    h = hashlib.sha256()
    with open(str(path), "rb") as fh:
        while True:
            b = fh.read(_CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# the ffmpeg roots this box has actually been measured to hold a
# working build, in the order they are tried.  The WinGet Links shim is the
# one that EXISTS here today (measured 2026-10-09: ffmpeg.exe / ffplay.exe /
# ffprobe.exe, 8.1.1-full_build-www.gyan.dev).
_TOOL_ROOTS = ("H:/ffmpeg/bin", "C:/ffmpeg/bin",
               "C:/Users/Administrador/AppData/Local/Microsoft/WinGet/Links")


def _tool(name):
    """The ffmpeg/ffprobe binary: the known install roots, then PATH.
    An external binary is a REAL_SUBSTITUTE, never a silent fallback, so the
    path actually used is named back to the caller in the measured block."""
    for root in _TOOL_ROOTS:
        for cand in (os.path.join(root, name), os.path.join(root, name + ".exe")):
            if os.path.isfile(cand):
                return cand
    try:
        r = subprocess.run(["where", name], capture_output=True, text=True)
    except OSError:
        r = None
    if r is not None and r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().splitlines()[0].strip()
    raise ClipToAsrError(
        "tool-missing",
        name + " was not found in any of " + ", ".join(_TOOL_ROOTS)
        + " nor on PATH; the clip cannot be processed")


def ffprobe_clip(clip):
    """The MEASURED shape of the clip: streams, duration, codec, fps.

    n_audio is reported on purpose: the capture this box ships today writes a
    VIDEO-ONLY clip (mp4_writer.cpp builds exactly one vide trak), so a real
    saved clip has nothing to extract and the gate's ffmpeg-built fixture is a
    stand-in for the muxed shape.  Saying so out loud is the point.
    """
    exe = _tool("ffprobe")
    cmd = [exe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(clip)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise ClipToAsrError("ffprobe-failed", (r.stderr or r.stdout).strip()[-600:])
    j = json.loads(r.stdout or "{}")
    streams = j.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None:
        raise ClipToAsrError("clip-no-video-stream",
                             str(clip) + " has no video stream (" + str(len(streams)) + " streams)")
    num, den = (v.get("r_frame_rate") or "0/1").split("/")
    try:
        fps = round(float(num) / float(den), 3) if float(den) else None
    except Exception:
        fps = None
    try:
        dur_ms = int(round(float(j["format"]["duration"]) * 1000))
    except Exception:
        dur_ms = int(round(float(v.get("duration") or 0) * 1000))
    return {
        "n_streams": len(streams),
        "n_video": sum(1 for s in streams if s.get("codec_type") == "video"),
        "n_audio": sum(1 for s in streams if s.get("codec_type") == "audio"),
        "has_audio": a is not None,
        "codec": v.get("codec_name"),
        "w": int(v.get("width") or 0),
        "h": int(v.get("height") or 0),
        "fps": fps,
        "duration_s": round(dur_ms / 1000.0, 3),
        "duration_ms": dur_ms,
        "bitrate": int(j["format"].get("bit_rate") or 0),
    }


def extract_wav(clip, wav, workdir=None):
    """clip -> 16000 Hz / mono / s16le wav, via ffmpeg, then VERIFIED.

    The audio format is REFUSED, never converted: 16000/mono/PCM16 is what the
    shipped ASR contract demands and this module will not quietly hand the
    model something else.
    """
    exe = _tool("ffmpeg")
    wav = Path(wav)
    wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(clip),
           "-map", "0:a:0", "-vn", "-sn", "-dn",
           "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le",
           "-f", "wav", str(wav)]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True,
                       cwd=str(workdir) if workdir else None)
    took = round(time.perf_counter() - t0, 3)
    if r.returncode != 0 or not wav.is_file():
        raise ClipToAsrError("wav-extract-failed",
                             "ffmpeg rc=" + str(r.returncode) + " " + (r.stderr or "").strip()[-400:],
                             {"ffmpeg_rc": r.returncode})
    import asr.audio as audio  # light import: numpy stays lazy inside it

    try:
        info = audio.wav_info(wav)
    except audio.WavFormatError as exc:
        raise ClipToAsrError("wav-contract-refused", str(exc))
    d = info.as_dict()
    if d["sample_rate"] != SAMPLE_RATE or d["channels"] != 1 or d["sampwidth"] != 2:
        raise ClipToAsrError(
            "wav-contract-refused",
            str(wav) + " is " + str(d["sample_rate"]) + "Hz/" + str(d["channels"]) + "ch/"
            + str(d["sampwidth"] * 8) + "bit; the contract is 16000/mono/PCM16 and nothing here converts")
    return {"path": str(wav), "seconds": took, "wav_info": d}


def seg_id_for(content_key, start_ms):
    """A deterministic, positive, signed-63-bit seg_id derived from the
    IDENTITY of the bytes -- never from a row counter or an AUTOINCREMENT.
    This is the whole idempotence fix for receipt 24 sec. 7.1."""
    h = hashlib.sha256(("sotto/seg|" + str(content_key) + "|" + str(int(start_ms)))
                       .encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") >> 1


def mint_seg_id(conn, *, video_id, content_key, start_ms):
    """Mint, then CHECK the mint: a seg_id already owned by a different
    (video_id, start_ms) is a hash collision and is refused loudly, because
    upsert_segment(seg_id=...) would otherwise silently re-point that row."""
    sid = seg_id_for(content_key, start_ms)
    row = conn.execute("SELECT video_id, start_ms FROM segment WHERE seg_id = ?", (sid,)).fetchone()
    if row is not None and (int(row[0]) != int(video_id) or int(row[1]) != int(start_ms)):
        raise ClipToAsrError(
            "seg-id-collision",
            "minted seg_id " + str(sid) + " is already owned by (video_id=" + str(row[0])
            + ", start_ms=" + str(row[1]) + "); wanted (video_id=" + str(video_id)
            + ", start_ms=" + str(start_ms) + ")", {"seg_id": sid})
    return sid


# ---------------------------------------------------------------------------
# phase 1 -- the part that must never wait for the model
# ---------------------------------------------------------------------------


def index_clip(conn, *, clip, content_key=None, state="indexed",
                stamp_scan=False):
    """hash + probe + upsert_video, COMMITTED.  No model, no ffmpeg, no numpy.

    The commit before returning is what makes arm D true: the video row is
    durable on disk before any ASR process is even spawned, so a stalled or
    dead worker cannot hold the clip's index entry hostage.

    stamp_scan is the ONE knob, and it defaults False on purpose.
    last_seen_scan is the clock of whoever SCANNED the library; phase 2 is not
    a scan and must not advance that clock, or the video row's own hash would
    move on every re-run and ARM-C would have nothing stable to compare.
    store.upsert_video already folds a NULL last_seen_scan into the existing
    value (COALESCE(excluded, video)), so not passing it is a no-op, not a
    NULL-out.  REJECTED alternative: stamp in the fingerprint's comparison as
    a volatile column -- that would have made the idempotence arm blind to the
    one field that most obviously lies about identity.
    """
    clip = Path(clip)
    if not clip.is_file():
        raise ClipToAsrError("bad-input", "clip does not exist: " + str(clip))
    t0 = time.perf_counter()
    key = content_key or sha256_path(clip)
    probe = ffprobe_clip(clip)
    st = clip.stat()
    video_id = store.upsert_video(
        conn,
        content_key=key,
        path=str(clip.resolve()),
        size_bytes=st.st_size,
        mtime_ns=st.st_mtime_ns,
        duration_ms=probe["duration_ms"],
        codec=probe["codec"],
        w=probe["w"],
        h=probe["h"],
        fps=probe["fps"],
        bitrate=probe["bitrate"],
        last_seen_scan=int(time.time()) if stamp_scan else None,
        missing=0,
        state=state,
    )
    conn.commit()
    return {
        "video_id": video_id,
        "content_key": key,
        "path": str(clip.resolve()),
        "size_bytes": st.st_size,
        "probe": probe,
        "index_ms": round((time.perf_counter() - t0) * 1000.0, 1),
    }


# ---------------------------------------------------------------------------
# phase 2 -- the ASR worker, run as a SEPARATE PROCESS
# ---------------------------------------------------------------------------


def _child_env(intra, inter):
    """Pin the ORT thread pool in the CHILD, before its numpy/ort import.

    Lane 11 measured that the pin bounds the ORT POOL, not the process:
    intra=1 puts 99.9 percent of the load on one core, intra=4 spreads it.
    The child is a fresh interpreter, so the pin has to be in its environment.
    """
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = str(intra)
    env["OPENBLAS_NUM_THREADS"] = str(inter)
    env["MKL_NUM_THREADS"] = str(inter)
    env["NUMEXPR_NUM_THREADS"] = str(inter)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def asr_cmdline(wav, *, provider, intra, inter, max_segment_s, asr_cmd, model_dir):
    """The worker command line.  --asr-cmd replaces it wholesale, and the wav
    path is ALWAYS the final argv so a stub worker can simply ignore it."""
    if asr_cmd:
        return shlex.split(asr_cmd) + [str(wav)]
    # the REAL flag names of asr.transcribe, read off its --help: --max-seg,
    # --threads, --inter-threads.  A typo here would be argparse's exit 2.
    return [sys.executable, "-m", "asr.transcribe",
            "--wav", str(wav),
            "--model-dir", str(model_dir),
            "--quant", "int8",
            "--segment-mode", DEFAULT_SEGMENT_MODE,
            "--max-seg", str(max_segment_s),
            "--threads", str(intra),
            "--inter-threads", str(inter),
            "--provider", provider,
            "--level", "off",
            "--json"]


def wav_duration_s(wav):
    import wave

    with wave.open(str(wav), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def run_asr(wav, *, provider="cpu", intra=INTRA_OP, inter=INTER_OP,
            max_segment_s=DEFAULT_MAX_SEGMENT_S, asr_cmd=None,
            timeout_s=None, env=None, cwd=None, model_dir=None):
    """Run the ASR worker as a separate process and return its done line.

    A worker that DIES, STALLS, or prints no parseable done line is a loud,
    SPECIFIC refusal -- never a silent empty transcript.  Making those three
    impossible to confuse is the whole reason this function exists.
    """
    cmd = asr_cmdline(wav, provider=provider, intra=intra, inter=inter,
                      max_segment_s=max_segment_s, asr_cmd=asr_cmd,
                      model_dir=str(Path(model_dir) if model_dir else _default_model_dir()))
    if timeout_s is None:
        # receipt 24 measured about 0.18x realtime on this box with this
        # recipe; the default leaves three orders of magnitude of headroom
        # and is overridable per call.
        try:
            timeout_s = max(120.0, 200.0 * wav_duration_s(wav))
        except Exception:
            timeout_s = 120.0
    t0 = time.perf_counter()
    if env is None:
        env = _child_env(intra, inter)
        # the child resolves the asr package from src/, NOT from the repo
        # root, where 'import asr' does not resolve at all.
        pp = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(_SRC) + (os.pathsep + pp if pp else "")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(cwd) if cwd else str(_SRC),
        creationflags=CREATE_NO_WINDOW,  # the owner is owed no console window
    )
    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            out, err = proc.communicate(timeout=10)
        except Exception:
            out, err = "", ""
        raise ClipToAsrError(
            "asr-worker-timeout",
            "the ASR worker did not finish within " + str(round(timeout_s, 1))
            + "s and was killed; this is a STALL, not a transcription",
            {"timeout_s": round(timeout_s, 1),
             "wall_s": round(time.perf_counter() - t0, 3)})
    wall = round(time.perf_counter() - t0, 3)
    if proc.returncode != 0:
        tail = (err or "").strip().splitlines()[-1] if (err or "").strip() else "(no stderr)"
        raise ClipToAsrError(
            "asr-worker-failed",
            "the ASR worker exited rc=" + str(proc.returncode)
            + " and produced no transcript: " + tail,
            {"rc": int(proc.returncode), "wall_s": wall})
    done = None
    for line in reversed([l for l in (out or "").splitlines() if l.strip()]):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict) and "segments" in obj:
            done = obj
            break
    if done is None:
        raise ClipToAsrError(
            "asr-worker-no-done",
            "the ASR worker exited 0 but printed no done line (stdout "
            + str(len(out or "")) + " B, stderr " + str(len(err or ""))
            + " B); rc 0 with no transcript is a refusal",
            {"rc": int(proc.returncode), "wall_s": wall})
    done["_wall_s"] = wall
    # the worker pid, so a caller that runs us can prove which pid tree any
    # window claim is about (ARM D2 of the gate samples the tracked pids).
    done["pid"] = proc.pid
    return done


def model_sha256(model_dir):
    """Identity of the weights we ran: sha256 over the sorted (name,size)
    inventory of the model dir.  Deliberately NOT a hash of the 670 MB of
    weights: reading them at index time would make the caller pay for the
    model's bytes just to be told which model it was."""
    items = [str(p.relative_to(model_dir).as_posix()) + ":" + str(p.stat().st_size)
             for p in sorted(Path(model_dir).rglob("*")) if p.is_file()]
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def _default_model_dir():
    return _REPO_ROOT / "models" / "parakeet-tdt-0.6b-v3-onnx"


# ---------------------------------------------------------------------------
# the speech row write
# ---------------------------------------------------------------------------
def _sha256_text(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def transcript_row(conn, seg_id):
    """The transcript row for one seg_id, or None."""
    cur = conn.execute("SELECT seg_id, start_ms, text, text_norm, producer, model_sha256"
                       " FROM transcript WHERE seg_id=?", (seg_id,))
    r = cur.fetchone()
    if r is None:
        return None
    return {"seg_id": r[0], "start_ms": r[1], "text": r[2], "text_norm": r[3],
            "producer": r[4], "model_sha256": r[5]}


def write_speech_row(conn, *, seg_id, text, start_ms, producer, model_sha256):
    """Make the speech row for ONE seg_id exist and be right.  Returns the action.

    Why this is not store.upsert_transcript(): src/index/schema.sql keeps
    text_fts current with triggers that use the FTS5 'delete' special-insert
    (tr_transcript_fts_ad, tr_transcript_fts_au; the same shape at
    tr_ocr_fts_ad and tr_ocr_fts_au).  FTS5 documents that command as available
    "only ... with external content and contentless tables"
    (https://sqlite.org/fts5.html#the_delete_command, section 6.3) and text_fts
    is an ordinary content-storing fts5 table, so the command is refused there:
    every form of it - rowid only, rowid + one column, all columns, no columns,
    and for a rowid that is not even present - raises
    sqlite3.OperationalError("SQL logic error") on this host.  Measured on
    SQLite 3.43.1 (python sqlite3) and on SQLite 3.51.1 (sqlite3.exe CLI), on a
    table built by hand with no trigger in the way, so it is the table type and
    not the trigger or the build.  Consequences, all measured:

      * INSERT of a NEW seg_id works (only tr_transcript_fts_ai fires),
      * UPDATE of a transcript row fails - it is the trigger, proven by the same
        statement succeeding after DROP TRIGGER tr_transcript_fts_au,
      * DELETE FROM transcript fails, while DELETE FROM text_fts WHERE rowid=?
        works.

    So the upsert arm of store.upsert_transcript is dead on this schema, and a
    re-run of the same clip reaches it.  This lane does not own schema.sql and
    may not add a UNIQUE constraint or repair the triggers, so it does the only
    thing that is both idempotent and honest: read the row first, and INSERT
    only when the row is absent.  A row that already IS the row this run would
    have written is left untouched - that is the whole of ARM-C, the second run
    changes nothing.  A row that exists and DISAGREES is a loud refusal, never a
    silent overwrite: this host cannot rewrite it.
    """
    want = {"text": text, "text_norm": text, "start_ms": int(start_ms),
            "producer": producer, "model_sha256": model_sha256}
    have = transcript_row(conn, seg_id)
    if have is not None:
        diff = [k for k, v in want.items() if have.get(k) != v]
        if not diff:
            return "kept"
        raise ClipToAsrError(
            "speech-row-conflict",
            "a transcript row already exists for seg_id=%d and it is NOT the row this run "
            "would write (differing fields: %s).  The row cannot be rewritten on this host: "
            "UPDATE and DELETE on transcript both fail with SQL logic error, because "
            "schema.sql maintains text_fts with triggers that use the FTS5 'delete' "
            "special-insert, which is only valid on external-content/contentless FTS "
            "tables.  Existing text sha256=%s, this run's text sha256=%s." % (
                seg_id, ",".join(diff),
                _sha256_text(have["text"]), _sha256_text(text)))
    store.upsert_transcript(conn, seg_id=seg_id, **want)
    return "inserted"


def asr_index(conn, *, clip, content_key=None, provider="cpu", intra=INTRA_OP,
              inter=INTER_OP, max_segment_s=DEFAULT_MAX_SEGMENT_S, asr_cmd=None,
              asr_timeout_s=None, tmpdir=None, keep_wav=False, model_dir=None):
    """Phase 2: the clip's audio becomes searchable, idempotently."""
    clip = Path(clip)
    if not clip.is_file():
        raise ClipToAsrError("bad-input", "clip does not exist: " + str(clip))
    work = (Path(tmpdir) if tmpdir else Path(tempfile.gettempdir())) / "sotto-clipasr"
    work.mkdir(parents=True, exist_ok=True)
    before = fingerprint(conn)

    head = index_clip(conn, clip=clip, content_key=content_key)
    video_id, key = head["video_id"], head["content_key"]
    wav = work / (key[:16] + ".wav")
    ext = extract_wav(clip, wav, workdir=work)
    done = run_asr(wav, provider=provider, intra=intra, inter=inter,
                   max_segment_s=max_segment_s, asr_cmd=asr_cmd,
                   timeout_s=asr_timeout_s, env=_child_env(intra, inter))

    mdir = Path(model_dir) if model_dir else _default_model_dir()
    model_id = model_sha256(mdir) if mdir.is_dir() else None
    rows = []
    actions = {}
    for r in (done.get("segments") or []):
        text = (r.get("text") or "").strip()
        if not text:
            continue  # a silence-only segment: no speech row, none fabricated
        start_ms = int(round(float(r["start"]) * 1000))
        end_ms = int(round(float(r["end"]) * 1000))
        sid = mint_seg_id(conn, video_id=video_id, content_key=key, start_ms=start_ms)
        store.upsert_segment(conn, video_id=video_id, start_ms=start_ms, end_ms=end_ms,
                             seg_id=sid, n_visual=0, n_speech=1, n_ocr=0, state="light")
        action = write_speech_row(conn, seg_id=sid, text=text, start_ms=start_ms,
                                  producer=SPEECH_CHANNEL, model_sha256=model_id)
        actions[action] = actions.get(action, 0) + 1
        rows.append({"seg_id": sid, "start_ms": start_ms, "end_ms": end_ms,
                     "chars": len(text), "row": action})
    conn.commit()
    after = fingerprint(conn)
    if not keep_wav:
        try:
            wav.unlink()
        except OSError:
            pass

    _asr_keys = ("label", "wav", "segment_mode", "n_segments", "seg_median_s", "seg_max_s",
                 "audio_s", "audio_processed_s", "load_s", "infer_s",
                 "rtfx_infer", "rtfx_steady", "rtfx_slice",
                 "provider_requested", "quantization",
                 "rss_start_mb", "rss_after_load_mb", "rss_peak_mb", "rss_peak_wset_mb",
                 "cpu_median_pct", "cpu_max_pct", "cpu_load_median_pct", "cpu_load_max_pct")
    return {
        "status": "ok",
        "channel": SPEECH_CHANNEL,
        "video": head,
        "extract": ext,
        "asr": {k: done.get(k) for k in _asr_keys if k in done},
        "session_providers": (done.get("threads") or {}).get("session_providers"),
        "model_sha256": model_id,
        "segments": rows,
        "n_speech_rows": len(rows),
        "row_actions": actions,
        "text": done.get("text"),
        "fingerprint_before": before,
        "fingerprint_after": after,
    }


# ---------------------------------------------------------------------------
# idempotence instrumentation
# ---------------------------------------------------------------------------

_FINGERPRINT_TABLES = ("index_meta", "video", "segment", "transcript", "text_fts",
                       "ocr", "embedding", "marker")


def fingerprint(conn):
    """A canonical, order-stable digest of every row of every index table.

    NOT a hash of the db FILE -- WAL bytes move for reasons that have nothing
    to do with identity -- a hash of the ROWS.  ARM-C compares this.
    """
    out = {}
    for t in _FINGERPRINT_TABLES:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(" + t + ")").fetchall()]
        if not cols:
            continue
        sel = ",".join('"' + c + '"' for c in cols)
        rows = conn.execute('SELECT ' + sel + ' FROM "' + t + '" ORDER BY rowid').fetchall()
        norm = [[None if v is None else (v if isinstance(v, (int, float)) else str(v))
                 for v in r] for r in rows]
        blob = json.dumps({"table": t, "columns": cols, "rows": norm},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        out[t] = {"rows": len(rows), "bytes": len(blob.encode("utf-8")),
                  "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest()}
    return out


def fingerprint_diff(a, b):
    """Which tables, and how many rows, moved between two fingerprints."""
    d = {}
    for t in sorted(set(a) | set(b)):
        ra, rb = a.get(t), b.get(t)
        if ra == rb:
            continue
        d[t] = {"rows": [ra["rows"] if ra else None, rb["rows"] if rb else None],
                "sha256": {"before": ra["sha256"][:12] if ra else None,
                           "after": rb["sha256"][:12] if rb else None}}
    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit(obj, *, as_json):
    if as_json:
        sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
    else:
        head = obj.get("video") or {}
        clip = head.get("path") or obj.get("clip", "")
        sys.stdout.write("CLIPTOASR status=" + str(obj.get("status", "?"))
                         + " clip=" + str(clip) + "\n")
        for k, v in obj.items():
            if k == "status":
                continue
            sys.stdout.write("CLIPTOASR   " + str(k) + "="
                             + json.dumps(v, sort_keys=True) + "\n")
    sys.stdout.flush()


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="clip_to_asr",
        description="step 5 indexing half: clip -> speech rows, idempotently, never blocking capture")
    ap.add_argument("phase", choices=("index", "asr", "all"), default="all", nargs="?")
    ap.add_argument("--clip", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", help="also write the JSON verdict to this path")
    ap.add_argument("--json", action="store_true",
                    help="print ONLY the JSON verdict on stdout")
    ap.add_argument("--provider", default="cpu", choices=("cpu", "cuda"))
    ap.add_argument("--intra-op", type=int, default=INTRA_OP)
    ap.add_argument("--inter-op", type=int, default=INTER_OP)
    ap.add_argument("--max-segment-s", type=float, default=DEFAULT_MAX_SEGMENT_S)
    ap.add_argument("--asr-cmd",
                    help="replace the worker command line wholesale (gate arms D and D2)")
    ap.add_argument("--asr-timeout-s", type=float, default=None)
    ap.add_argument("--tmpdir", default=None)
    ap.add_argument("--keep-wav", action="store_true")
    ap.add_argument("--model-dir", default=None)
    args = ap.parse_args(argv)

    if args.intra_op <= 0 or args.inter_op <= 0:
        _emit({"status": "bad-input", "clip": args.clip,
               "message": "intra_op=" + str(args.intra_op) + " inter_op="
                          + str(args.inter_op) + "; both must be > 0"},
              as_json=args.json)
        return 2

    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = store.connect(db, create=True)
    try:
        if args.phase == "index":
            verdict = {"status": "index-only", "clip": args.clip,
                       "video": index_clip(conn, clip=Path(args.clip),
                                           stamp_scan=True)}
        else:
            verdict = asr_index(conn, clip=Path(args.clip), provider=args.provider,
                                intra=args.intra_op, inter=args.inter_op,
                                max_segment_s=args.max_segment_s, asr_cmd=args.asr_cmd,
                                asr_timeout_s=args.asr_timeout_s, tmpdir=args.tmpdir,
                                keep_wav=args.keep_wav, model_dir=args.model_dir)
    except ClipToAsrError as exc:
        # THE VIDEO ROW SURVIVES AN ASR FAILURE.  Report what is ACTUALLY in
        # the index, so the empty speech channel says itself instead of being
        # inferred from a number that is not there.
        try:
            n_v = conn.execute("SELECT COUNT(*) FROM video").fetchone()[0]
            n_t = conn.execute("SELECT COUNT(*) FROM transcript").fetchone()[0]
            n_s = conn.execute("SELECT COUNT(*) FROM segment WHERE n_speech=1").fetchone()[0]
            conn.commit()
        except Exception:
            n_v = n_t = n_s = -1
        verdict = {"status": exc.status, "clip": args.clip, "message": str(exc),
                   "measured": exc.measured,
                   "index_state": {"video_rows": n_v, "speech_segments": n_s,
                                   "transcript_rows": n_t}}
        _emit(verdict, as_json=args.json)
        if args.out:
            Path(args.out).write_text(json.dumps(verdict, sort_keys=True), encoding="utf-8")
        return 3 if exc.status.startswith("asr-") or exc.status == "wav-contract-refused" else 2

    _emit(verdict, as_json=args.json)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(verdict, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
