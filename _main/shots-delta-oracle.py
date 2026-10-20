#!/usr/bin/env python3
"""ORACLE for the DELTA OF THE DESIGN LANE -- the cache must not be able to lie.

Owner (2026-10-20, verbatim: *"faz cache e teste incremental/delta e etc pra tu
parar de re rodar tudo do zero TODA HORA"*).

WHAT THIS PINS
--------------
`_main/_design-lane/intake-shots.py` re-rendered all 144 jobs of the design
intake on every invocation (~13 minutes of headless Edge) to produce the SAME
PNGs. It is now incremental: only the jobs whose INPUTS changed are rendered,
and the result the other jobs had is carried over. The rules live in
`_main/_design-lane/shots-delta.py`.

A cache that can lie is worse than no cache, so this oracle pins the HONESTY
RULE job by job:

  * a job is a HIT only when there is an entry for its name, the fingerprint
    computed NOW equals the recorded one, the output PNG still EXISTS and is
    still the SAME BYTES, and the output JSON (when there is one) still EXISTS
    and is still the SAME BYTES;
  * if ANY of those fails -> MISS, and the job runs again. A failure is never
    reused as if it were a pass;
  * a job with NO input at all has no fingerprint and can therefore NEVER be a
    hit;
  * a state file that does not exist, or that is CORRUPT, is a MISS for every
    job -- and the corruption is REPORTED, not swallowed;
  * the input is the CONTENT: the document the `url` points to, the source
    files that feed the render, the `eval` script, the image parameters and
    the output path. A `touch` changes nothing; a rewrite with the same bytes
    changes nothing; a change of any of them re-renders the job.

ARMS (pure: files in a temp dir; no browser, no network, no app, no audio)
    nothing changed -> HIT; the input document changed -> MISS; the output PNG
    deleted -> MISS; the output PNG MODIFIED -> MISS; the output JSON deleted
    -> MISS; the output JSON MODIFIED -> MISS; the state file does not exist
    -> MISS for all; the state file is CORRUPT -> MISS for all and it is
    reported; the parameters changed (w/h/keys/clip) -> MISS; the output path
    changed -> MISS; the `eval` script changed -> MISS; a job with no input is
    never a HIT; a state with a malformed shape -> MISS for all and it is
    reported; this theme's own sheet changed -> MISS; another theme's SCOPED
    rule changed -> HIT (it cannot reach this theme); another theme's
    `@keyframes` changed -> MISS (a keyframe is global); the shared sheet
    changed -> MISS; a recorded fingerprint that is not the computed one ->
    MISS; and `intake-shots.py` splits the plan into the jobs it skips and the
    jobs it runs.

NEGATIVE ARM (executed, not decorative)
    Eleven mutants of `_main/_design-lane/shots-delta.py` and
    `_main/_design-lane/intake-shots.py`, each a TEXTUAL patch of a UNIQUE
    anchor. A mutant whose anchor is missing or ambiguous is DECORATIVE -- it
    proves nothing -- so the oracle refuses to count it, and a mutant that
    loads but changes nothing is reported as SURVIVED (the gate is blind
    there).

Usage:
    python _main/shots-delta-oracle.py            # arms + mutants, rc=0 on PASS
    python _main/shots-delta-oracle.py --neg-arm  # mutants only, rc=1 BY DESIGN
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LANE = os.path.join(REPO, "_main", "_design-lane")
DELTA_PATH = os.path.join(LANE, "shots-delta.py")
INTAKE_PATH = os.path.join(LANE, "intake-shots.py")

EXIT_PASS = 0
EXIT_FAIL = 1


# ── the lane under test ──────────────────────────────────────────────────────

def build_lane(workdir, delta_source=None, intake_source=None):
    """A whole lane in a temp dir: shots-delta.py, shot.py, panel-measure.py
    and intake-shots.py -- with the two files under test optionally MUTATED.

    The lane is a COPY, so a mutant never touches the repository. The copy of
    `shot.py`/`panel-measure.py` is what `intake-shots.py` imports, so the
    lane loads exactly as the product's lane does.
    """
    lane = os.path.join(workdir, "lane")
    os.makedirs(lane, exist_ok=True)
    for name in ("shot.py", "panel-measure.py"):
        shutil.copyfile(os.path.join(LANE, name), os.path.join(lane, name))
    with open(DELTA_PATH, "r", encoding="utf-8", newline="") as fh:
        delta_text = fh.read()
    with open(INTAKE_PATH, "r", encoding="utf-8", newline="") as fh:
        intake_text = fh.read()
    if delta_source is not None:
        delta_text = delta_source
    if intake_source is not None:
        intake_text = intake_source
    with open(os.path.join(lane, "shots-delta.py"), "w", encoding="utf-8", newline="") as fh:
        fh.write(delta_text)
    with open(os.path.join(lane, "intake-shots.py"), "w", encoding="utf-8", newline="") as fh:
        fh.write(intake_text)
    return lane


def load_lane(lane):
    """(delta, intake) loaded FROM the lane dir, so a mutated shots-delta.py is
    the one intake-shots.py imports."""
    for name in ("shots_delta", "shot", "panel_measure", "intake_shots"):
        sys.modules.pop(name, None)
    sys.path.insert(0, lane)
    try:
        spec = importlib.util.spec_from_file_location(
            "shots_delta", os.path.join(lane, "shots-delta.py"))
        delta = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(delta)
        spec = importlib.util.spec_from_file_location(
            "intake_shots", os.path.join(lane, "intake-shots.py"))
        intake = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(intake)
    finally:
        try:
            sys.path.remove(lane)
        except ValueError:
            pass
    return delta, intake


# ── the fixtures ─────────────────────────────────────────────────────────────

def fixture(workdir, name="job-a"):
    """A tiny job: an input document, an `eval` script, a PNG and a JSON."""
    d = os.path.join(workdir, name.replace("/", "_"))
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "input.html")
    with open(src, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("<html><body>the demo</body></html>\n")
    script = os.path.join(d, "probe.js")
    with open(script, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* the probe */\n")
    out = os.path.join(d, "shot.png")
    with open(out, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    out_json = os.path.join(d, "shot.json")
    with open(out_json, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('{"captions": []}\n')
    job = {
        "name": name, "set": "demo",
        "url": "file:///" + src.replace(os.sep, "/"),
        "w": 1600, "h": 1000, "dsf": 1, "keys": ["1"], "wait": 2600,
        "clip": None, "out": out, "eval": script, "outJson": out_json,
    }
    return {"dir": d, "src": src, "eval": script, "out": out, "json": out_json,
            "job": job, "state": os.path.join(d, "state.json")}


def fixture_srcroot(workdir, name="job-theme-1"):
    """A job whose render reads a WORKDIR: the built document, the shared
    sheet, and the sheets of two themes (one own, one not)."""
    d = os.path.join(workdir, name.replace("/", "_"))
    os.makedirs(d, exist_ok=True)
    sheets = {
        "panel.html": "<html data-theme='theme-1'><body>the panel</body></html>\n",
        "panel.css": ".a { color: #fff; }\n",
        "themes/theme-1.css":
            ":root[data-theme='theme-1'] .a { color: #111; }\n"
            "@keyframes sotto-caret { 0%, 49% { opacity: 1; } "
            "50%, 100% { opacity: 0; } }\n",
        "themes/theme-2.css":
            ":root[data-theme='theme-2'] .b { color: #222; }\n"
            "@keyframes sotto-caret { 0%, 49% { opacity: 1; } "
            "50%, 100% { opacity: 0; } }\n",
    }
    for rel, body in sheets.items():
        path = os.path.join(d, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
    out = os.path.join(d, "shot.png")
    with open(out, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + b"1" * 32)
    out_json = os.path.join(d, "shot.json")
    with open(out_json, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('{"captions": []}\n')
    job = {
        "name": name, "set": "current",
        "url": "file:///" + os.path.join(d, "panel.html").replace(os.sep, "/"),
        "w": 380, "h": 900, "dsf": 1, "keys": [], "wait": 7000,
        "clip": None, "srcRoot": d, "theme": "theme-1",
        "out": out, "eval": os.path.join(d, "probe.js"), "outJson": out_json,
    }
    with open(job["eval"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* the probe */\n")
    return {"dir": d, "out": out, "json": out_json, "job": job,
            "state": os.path.join(workdir, name.replace("/", "_") + "-state.json"),
            "sheet1": os.path.join(d, "themes", "theme-1.css"),
            "sheet2": os.path.join(d, "themes", "theme-2.css"),
            "shared": os.path.join(d, "panel.css")}


def warm(delta, fx):
    """A state that says this job already ran, and it is on disk."""
    state, err = delta.load_state(fx["state"])
    if err:
        return None, err
    entry, reason = delta.record(fx["job"], {"name": fx["job"]["name"]}, state)
    if entry is None:
        return None, reason
    delta.save_state(state, fx["state"])
    return state, "ok"


def rewrite(path, old, new):
    """Replace a piece of a file, keeping its bytes otherwise. A same-size
    rewrite is the STRONGEST proof that the sha256 is what decides, and not
    the size."""
    with open(path, "rb") as fh:
        body = fh.read()
    if isinstance(old, str):
        old = old.encode("utf-8")
        new = new.encode("utf-8")
    if old not in body:
        return False
    with open(path, "wb") as fh:
        fh.write(body.replace(old, new, 1))
    return True


# ── the battery ──────────────────────────────────────────────────────────────

def battery(delta, intake, workdir):
    """The arms. Every one of them is pure: files in a temp dir, no browser,
    no network, no app, no audio."""
    rows = []

    def attempt(name, fn):
        try:
            ok, detail = fn()
        except Exception as exc:                            # noqa: BLE001
            ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
        rows.append((bool(ok), name, detail))

    # -- 1. nothing changed -> HIT ------------------------------------------
    def a01():
        fx = fixture(os.path.join(workdir, "a01"))
        state, _ = warm(delta, fx)
        hit, reason = delta.decide(fx["job"], None, state)
        ok = hit and reason == "ok"
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a01 nada mudou -> HIT (o job e saltado)", a01)

    # -- 2. the INPUT DOCUMENT changed -> MISS --------------------------------
    def a02():
        fx = fixture(os.path.join(workdir, "a02"))
        state, _ = warm(delta, fx)
        with open(fx["src"], "a", encoding="utf-8", newline="\n") as fh:
            fh.write("<!-- the document changed -->\n")
        hit, reason = delta.decide(fx["job"], None, state)
        ok = (not hit) and reason.startswith("fingerprint")
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a02 o FICHEIRO DE ENTRADA mudou -> MISS", a02)

    # -- 3. the output PNG was DELETED -> MISS --------------------------------
    def a03():
        fx = fixture(os.path.join(workdir, "a03"))
        state, _ = warm(delta, fx)
        os.remove(fx["out"])
        hit, reason = delta.decide(fx["job"], None, state)
        ok = (not hit) and reason.startswith("shot-missing")
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a03 o PNG de saida foi APAGADO -> MISS", a03)

    # -- 4. the output PNG was MODIFIED -> MISS -------------------------------
    def a04():
        fx = fixture(os.path.join(workdir, "a04"))
        state, _ = warm(delta, fx)
        ok_write = rewrite(fx["out"], b"0" * 32, b"9" * 32)
        hit, reason = delta.decide(fx["job"], None, state)
        ok = ok_write and (not hit) and reason.startswith("shot-changed")
        return ok, "hit=%r reason=%r (same size, other bytes)" % (hit, reason)
    attempt("a04 o PNG de saida foi MODIFICADO -> MISS", a04)

    # -- 5. the output JSON was DELETED -> MISS -------------------------------
    def a05():
        fx = fixture(os.path.join(workdir, "a05"))
        state, _ = warm(delta, fx)
        os.remove(fx["json"])
        hit, reason = delta.decide(fx["job"], None, state)
        ok = (not hit) and reason.startswith("json-missing")
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a05 o JSON de saida foi APAGADO -> MISS", a05)

    # -- 6. the output JSON was MODIFIED -> MISS ------------------------------
    def a06():
        fx = fixture(os.path.join(workdir, "a06"))
        state, _ = warm(delta, fx)
        ok_write = rewrite(fx["json"], "[]", "[1]")
        hit, reason = delta.decide(fx["job"], None, state)
        ok = ok_write and (not hit) and reason.startswith("json-changed")
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a06 o JSON de saida foi MODIFICADO -> MISS", a06)

    # -- 7. the state file does not exist -> MISS for all ---------------------
    def a07():
        fx = fixture(os.path.join(workdir, "a07"))
        state, _ = warm(delta, fx)
        os.remove(fx["state"])
        state2, err = delta.load_state(fx["state"])
        hit, reason = delta.decide(fx["job"], None, state2)
        ok = err is None and (not hit) and reason.startswith("no-entry")
        return ok, "hit=%r reason=%r err=%r" % (hit, reason, err)
    attempt("a07 o ficheiro de estado NAO EXISTE -> MISS para todos", a07)

    # -- 8. the state file is CORRUPT -> MISS for all, and it is REPORTED -----
    def a08():
        fx = fixture(os.path.join(workdir, "a08"))
        state, _ = warm(delta, fx)
        with open(fx["state"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write("this is not json at all\n")
        state2, err = delta.load_state(fx["state"])
        hit, reason = delta.decide(fx["job"], None, state2)
        ok = (err is not None) and (not hit) and reason.startswith("no-entry")
        return ok, "hit=%r reason=%r err=%r" % (hit, reason, err)
    attempt("a08 o estado esta CORROMPIDO -> MISS para todos e e REPORTADO", a08)

    # -- 9. the PARAMETERS changed -> MISS -----------------------------------
    def a09():
        fx = fixture(os.path.join(workdir, "a09"))
        state, _ = warm(delta, fx)
        details = []
        ok = True
        for key, value in (("w", 1601), ("h", 901), ("keys", ["2"]), ("clip", ".x")):
            job = dict(fx["job"])
            job[key] = value
            hit, reason = delta.decide(job, None, state)
            details.append("%s->%s:%r" % (key, "MISS" if not hit else "HIT", reason))
            if hit or not reason.startswith("fingerprint"):
                ok = False
        return ok, " ".join(details)
    attempt("a09 os PARAMETROS do job mudaram (w/h/keys/clip) -> MISS", a09)

    # -- 10. the OUTPUT PATH changed -> MISS ---------------------------------
    def a10():
        fx = fixture(os.path.join(workdir, "a10"))
        state, _ = warm(delta, fx)
        other = os.path.join(fx["dir"], "elsewhere.png")
        shutil.copyfile(fx["out"], other)
        job = dict(fx["job"])
        job["out"] = other
        hit, reason = delta.decide(job, None, state)
        ok = (not hit) and reason.startswith("fingerprint")
        return ok, "hit=%r reason=%r (the same bytes, another path)" % (hit, reason)
    attempt("a10 o `out` (caminho de saida) mudou -> MISS", a10)

    # -- 11. the `eval` SCRIPT changed -> MISS -------------------------------
    def a11():
        fx = fixture(os.path.join(workdir, "a11"))
        state, _ = warm(delta, fx)
        ok_write = rewrite(fx["eval"], "the probe", "other probe")
        hit, reason = delta.decide(fx["job"], None, state)
        ok = ok_write and (not hit) and reason.startswith("fingerprint")
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a11 o script `eval` mudou -> MISS", a11)

    # -- 12. a job with NO INPUT is never a HIT ------------------------------
    def a12():
        fx = fixture(os.path.join(workdir, "a12"))
        state, _ = warm(delta, fx)
        broken = dict(fx["job"])
        broken["url"] = "file:///" + os.path.join(fx["dir"], "not-here.html").replace(os.sep, "/")
        no_url = dict(fx["job"])
        no_url.pop("url")
        no_url["name"] = "job-b"
        details = []
        ok = True
        for job in (broken, no_url):
            fp = delta.fingerprint(job)
            hit, reason = delta.decide(job, None, state)
            details.append("%s:fp=%r hit=%r" % (job.get("name"), fp, hit))
            if fp is not None or hit:
                ok = False
        return ok, " ".join(details)
    attempt("a12 um job SEM INPUT nenhum NUNCA e HIT", a12)

    # -- 13. a state with a MALFORMED shape -> MISS for all, and REPORTED ----
    def a13():
        fx = fixture(os.path.join(workdir, "a13"))
        state, _ = warm(delta, fx)
        with open(fx["state"], "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"version": 1, "jobs": "not-an-object"}, fh)
        state2, err = delta.load_state(fx["state"])
        hit, reason = delta.decide(fx["job"], None, state2)
        ok = (err is not None) and (not hit) and reason.startswith("no-entry")
        return ok, "hit=%r reason=%r err=%r" % (hit, reason, err)
    attempt("a13 o estado e MALFORMADO -> MISS para todos e e REPORTADO", a13)

    # -- 14. THIS theme's own sheet changed -> MISS --------------------------
    def a14():
        fx = fixture_srcroot(os.path.join(workdir, "a14"))
        state, _ = warm(delta, fx)
        ok_write = rewrite(fx["sheet1"], "#111", "#112")
        hit, reason = delta.decide(fx["job"], None, state)
        ok = ok_write and (not hit) and reason.startswith("fingerprint")
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a14 a folha do PROPRIO tema mudou -> MISS", a14)

    # -- 15. another theme's SCOPED rule changed -> HIT ----------------------
    def a15():
        fx = fixture_srcroot(os.path.join(workdir, "a15"))
        state, _ = warm(delta, fx)
        ok_write = rewrite(fx["sheet2"], "#222", "#223")
        hit, reason = delta.decide(fx["job"], None, state)
        ok = ok_write and hit
        return ok, "hit=%r reason=%r (a regra de outro tema nao chega aqui)" % (hit, reason)
    attempt("a15 a regra ESCOPADA de outro tema mudou -> HIT", a15)

    # -- 16. another theme's @keyframes changed -> MISS ----------------------
    def a16():
        fx = fixture_srcroot(os.path.join(workdir, "a16"))
        state, _ = warm(delta, fx)
        ok_write = rewrite(fx["sheet2"], "opacity: 0; } }", "opacity: 0.5; } }")
        hit, reason = delta.decide(fx["job"], None, state)
        ok = ok_write and (not hit) and reason.startswith("fingerprint")
        return ok, "hit=%r reason=%r (um @keyframes e global)" % (hit, reason)
    attempt("a16 o @keyframes de outro tema mudou -> MISS", a16)

    # -- 17. the SHARED sheet changed -> MISS --------------------------------
    def a17():
        fx = fixture_srcroot(os.path.join(workdir, "a17"))
        state, _ = warm(delta, fx)
        ok_write = rewrite(fx["shared"], "#fff", "#eee")
        hit, reason = delta.decide(fx["job"], None, state)
        ok = ok_write and (not hit) and reason.startswith("fingerprint")
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a17 a folha PARTILHADA mudou -> MISS", a17)

    # -- 18. the recorded fingerprint is NOT the computed one -> MISS ---------
    def a18():
        fx = fixture(os.path.join(workdir, "a18"))
        state, _ = warm(delta, fx)
        entry = state["jobs"][fx["job"]["name"]]
        entry["fingerprint"] = "0" * 64
        hit, reason = delta.decide(fx["job"], None, state)
        ok = (not hit) and reason.startswith("fingerprint")
        return ok, "hit=%r reason=%r" % (hit, reason)
    attempt("a18 o fingerprint gravado NAO e o calculado -> MISS", a18)

    # -- 19. the lane SPLITS the plan: the unchanged is skipped --------------
    def a19():
        one = fixture(os.path.join(workdir, "a19"), "job-a")
        two = fixture(os.path.join(workdir, "a19"), "job-b")
        state = {"version": 1, "jobs": {}}
        for fx in (one, two):
            delta.record(fx["job"], {"name": fx["job"]["name"]}, state)
        with open(two["src"], "a", encoding="utf-8", newline="\n") as fh:
            fh.write("<!-- changed -->\n")
        hits, misses = intake.split_jobs([one["job"], two["job"]], state)
        ok = ([j["name"] for j in hits] == ["job-a"]
              and [j["name"] for j in misses] == ["job-b"])
        return ok, "hits=%r misses=%r" % ([j["name"] for j in hits],
                                          [j["name"] for j in misses])
    attempt("a19 a lane salta o que nao mudou e corre o que mudou", a19)

    return rows


# ── the mutants ─────────────────────────────────────────────────────────────
# The anchors are EXACT strings of the two files under test. A mutant whose
# anchor is missing or ambiguous is DECORATIVE -- it proves nothing -- so the
# oracle refuses to count it.

MUTANTS = [
    # THE ARTEFACT RULE IS GONE: the PNG may be deleted, or replaced by
    # another run's PNG, and the job is still a HIT -- the cache now serves a
    # picture that is not there.
    ("a-artefacto-pode-desaparecer",
     "shots-delta.py",
     '    out = job.get("out")\n'
     '    if not out or not os.path.isfile(out):\n'
     '        return False, "shot-missing: %s" % out\n'
     '    if sha256_file(out) != entry.get("out_sha256"):\n'
     '        return False, "shot-changed: %s" % out\n',
     '    out = job.get("out")  # MUTANT: the artefact rule is gone\n'),
    # THE PNG's sha256 IS NOT CHECKED: only its existence is. A PNG that
    # another run overwrote is served as if it were this job's.
    ("o-sha256-do-png-nao-e-verificado",
     "shots-delta.py",
     '    if sha256_file(out) != entry.get("out_sha256"):\n'
     '        return False, "shot-changed: %s" % out\n',
     '    pass  # MUTANT: only the existence of the PNG is checked\n'),
    # THE JSON's sha256 IS NOT CHECKED: the measurement that the job
    # produced is served as if it were the one that was recorded.
    ("o-sha256-do-json-nao-e-verificado",
     "shots-delta.py",
     '        if sha256_file(out_json) != entry.get("outJson_sha256"):\n'
     '            return False, "json-changed: %s" % out_json\n',
     '        pass  # MUTANT: the bytes of the JSON are not checked\n'),
    # THE OUTPUT PATH LEAVES THE FINGERPRINT: the same input rendered to
    # another file is not a new job -- the OLD picture is served.
    ("o-out-sai-do-fingerprint",
     "shots-delta.py",
     '    parts.append(("out", str(job.get("out") or "")))\n',
     '    pass  # MUTANT: the output path is not part of the fingerprint\n'),
    # THE `eval` SCRIPT LEAVES THE FINGERPRINT: a new probe -- a different
    # measurement -- is served with the old numbers.
    ("o-eval-sai-do-fingerprint",
     "shots-delta.py",
     '    script = job.get("eval")\n'
     '    if script:\n'
     '        digest = sha256_file(script)\n'
     '        if not digest:\n'
     '            return None\n'
     '        parts.append(("eval", digest))\n',
     '    pass  # MUTANT: the eval script is not part of the fingerprint\n'),
    # A CORRUPT STATE IS TREATED AS VALID: the cache that was thrown away
    # is thrown away SILENTLY, and nobody knows the delta is not working.
    ("o-estado-corrompido-e-um-estado-valido",
     "shots-delta.py",
     '    except (OSError, ValueError) as exc:\n'
     '        return empty, "state-unreadable: %s: %s" % (type(exc).__name__, exc)\n',
     '    except (OSError, ValueError) as exc:\n'
     '        return empty, None\n'),
    # A MALFORMED STATE IS TREATED AS VALID: the same, for the other kind of
    # corruption.
    ("o-estado-malformado-e-um-estado-valido",
     "shots-delta.py",
     '    if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict):\n'
     '        return empty, "state-malformed: no \'jobs\' object"\n',
     '    if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict):\n'
     '        return empty, None\n'),
    # THE SOURCE FILES LEAVE THE FINGERPRINT: a stylesheet that changed --
    # and the picture it paints changed with it -- is not noticed.
    ("os-ficheiros-de-origem-saim-do-fingerprint",
     "shots-delta.py",
     '    root = job.get("srcRoot")\n'
     '    if root and os.path.isdir(root):\n'
     '        rows = workdir_digests(root, job.get("theme"))\n'
     '        if rows is None:\n'
     '            return None\n'
     '        parts.extend(rows)\n',
     '    pass  # MUTANT: the source files are not part of the fingerprint\n'),
    # A JOB WITH NO INPUT CAN BE A HIT: the one job that can never be
    # trusted is the one that is trusted the most.
    ("um-job-sem-input-pode-ser-hit",
     "shots-delta.py",
     '    if not fp:\n'
     '        return False, "no-input: a job with no input can never be trusted"\n',
     '    if not fp:\n'
     '        fp = entry.get("fingerprint")\n'),
    # THE RECORDED FINGERPRINT IS NEVER COMPARED: every job is a HIT, and
    # the delta is a "skip everything".
    ("o-fingerprint-gravado-nunca-e-comparado",
     "shots-delta.py",
     '    if entry.get("fingerprint") != fp:\n'
     '        return False, "fingerprint: the inputs changed"\n',
     '    pass  # MUTANT: the recorded fingerprint is never compared\n'),
    # THE LANE SKIPS EVERYTHING: every job is a HIT, so the lane never
    # renders anything again -- and the pictures rot in silence.
    ("a-lane-salta-tudo",
     "intake-shots.py",
     '        hit, _reason = shots_delta.decide(job, entry, state, fp)\n',
     '        hit, _reason = True, "mutant: every job is a hit"\n'),
]


def main() -> int:
    neg_only = "--neg-arm" in sys.argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                           # noqa: BLE001
        pass
    if not os.path.isfile(DELTA_PATH) or not os.path.isfile(INTAKE_PATH):
        print("RED   the lane is missing: %s / %s" % (DELTA_PATH, INTAKE_PATH))
        return EXIT_FAIL
    with open(DELTA_PATH, "r", encoding="utf-8", newline="") as fh:
        delta_text = fh.read()
    with open(INTAKE_PATH, "r", encoding="utf-8", newline="") as fh:
        intake_text = fh.read()

    arms_total = arms_green = 0
    if not neg_only:
        print("ARMS (pure: files in a temp dir; no browser, no network, no app, "
              "no audio)")
        workdir = tempfile.mkdtemp(prefix="shots-delta-oracle-")
        try:
            lane = build_lane(workdir)
            delta, intake = load_lane(lane)
            rows = battery(delta, intake, workdir)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        for ok, name, detail in rows:
            print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                                 ("  " + detail) if detail else ""))
        arms_green = sum(1 for ok, _, _ in rows if ok)
        arms_total = len(rows)
        print("\n  %d/%d" % (arms_green, arms_total))

    print("\nNEGATIVE ARM (broken copies must go RED)")
    caught = 0
    weak = 0
    workdir = tempfile.mkdtemp(prefix="shots-delta-oracle-mut-")
    try:
        for idx, (label, fname, old, new) in enumerate(MUTANTS):
            source = delta_text if fname == "shots-delta.py" else intake_text
            hits = source.count(old)
            if hits != 1:
                print("  RED   mutant %-46s ANCHOR %s -- oracle is stale"
                      % (label, "MISSING" if hits == 0 else "AMBIGUOUS"))
                weak += 1
                continue
            lane = build_lane(workdir,
                              delta_source=(source.replace(old, new, 1)
                                            if fname == "shots-delta.py"
                                            else delta_text),
                              intake_source=(source.replace(old, new, 1)
                                             if fname == "intake-shots.py"
                                             else intake_text))
            try:
                bad_delta, bad_intake = load_lane(lane)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-46s DECORATIVO: nao carregou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            sub = tempfile.mkdtemp(prefix="shots-delta-oracle-mut-run-")
            try:
                res = battery(bad_delta, bad_intake, sub)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-46s a bateria rebentou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            finally:
                shutil.rmtree(sub, ignore_errors=True)
            reds = [name for ok, name, _ in res if not ok]
            if reds:
                print("  GREEN mutant %-46s caught by: %s"
                      % (label, "; ".join(reds[:3])))
                caught += 1
            else:
                print("  RED   mutant %-46s SURVIVED -- the gate is blind here"
                      % label)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    total = len(MUTANTS)
    if neg_only:
        print("\nVERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por desenho: o braco "
              "negativo tem de falhar)" % ("PASS" if caught == total else "FAIL",
                                           caught, total))
        return EXIT_FAIL if caught == total else EXIT_PASS
    ok = arms_green == arms_total and caught == total and weak == 0
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", arms_green, arms_total, caught, total))
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
