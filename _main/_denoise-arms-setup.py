# -*- coding: utf-8 -*-
"""Stage the three arms of the denoise A/B so that ONLY the variable differs.

WHY BOTH ARMS LIVE IN ONE PARENT AND NONE OF THEM RUNS FROM `worker/`.

Arm A (OFF) is the live revision minus this lane's four insertions. Arm B (ON)
is a byte-identical COPY of the live revision. If A ran from
`_main/denoise-frozen/off/` and B from `worker/`, the two processes would differ
in their SCRIPT DIRECTORY as well as in their bytes -- and this worker resolves
things from `HERE` (`--config` default, `model.dir`, `assets/sample1.flac`,
`__file__`-relative paths), so "same argv" would not mean "same inputs". Put
both revisions in sibling directories with the SAME support modules beside each
one, pass absolute `--model --config --audio`, and the remaining difference is
exactly one file.

THE SUPPORT MODULES ARE PART OF THE ARM, NOT DECORATION. `import lang_prompt`
and `import wasapi_loopback` are resolved through `sys.path[0]`, which for a
script is the script's OWN directory -- so a copy of the worker parked in
`_main/` without `lang_prompt.py` next to it dies on import. That trap cost a
previous lane a run; the copies here are the fix, and both are verified by
sha256 against the originals so an arm can never quietly drift from `worker/`.

`denoise.py` is copied beside BOTH arms. Arm A does not import it (it has no
reference to this lane at all -- that is asserted in `_denoise-patch.py`); the
copy is there so both directories are structurally identical.

THE CONFIGS ARE BUILT, NOT TYPED. Both are parsed from the live
`worker/config.json`, and `config-true.json` is written by toggling ONE key, so
the pair cannot drift in anything else. The live config is what the OWNER's app
reads: it is opened read-only here and never written.

USAGE
    py -3 _main/_denoise-arms-setup.py
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORKER = os.path.join(REPO, "worker")
FROZEN = os.path.join(HERE, "denoise-frozen")
OFF = os.path.join(FROZEN, "off")
ON = os.path.join(FROZEN, "on")

LIVE_WORKER = os.path.join(WORKER, "sotto_worker.py")
LIVE_CONFIG = os.path.join(WORKER, "config.json")
SUPPORT = ("lang_prompt.py", "wasapi_loopback.py", "denoise.py")

# Recorded before this lane's edit and re-derived by `_denoise-patch.py`; the
# arm is REFUSED if either hash is not what the receipt will claim.
OFF_ARM_SHA = "64E7EC6F6C35C33600E9D50C11AC7D8CE96FBE1FEF87C24CD628BDF03F314E61"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    problems = []

    live_bytes = open(LIVE_WORKER, "rb").read()
    live_sha = sha(live_bytes)
    print("live worker   %d B  sha256 %s" % (len(live_bytes), live_sha))

    os.makedirs(OFF, exist_ok=True)
    os.makedirs(ON, exist_ok=True)

    off_path = os.path.join(OFF, "sotto_worker.py")
    if not os.path.exists(off_path):
        problems.append("OFF arm missing -- run _denoise-patch.py --off-out %s" % off_path)
    else:
        off_bytes = open(off_path, "rb").read()
        print("off  worker   %d B  sha256 %s" % (len(off_bytes), sha(off_bytes)))
        if sha(off_bytes).upper() != OFF_ARM_SHA:
            problems.append("OFF arm is not the pre-edit revision %s" % OFF_ARM_SHA)
        if b"denoise" in off_bytes.lower():
            problems.append("OFF arm mentions denoise")

    # Arm B is a COPY, and it is re-copied every time so it can never be a stale
    # leftover of a newer revision.
    shutil.copyfile(LIVE_WORKER, os.path.join(ON, "sotto_worker.py"))
    on_sha = sha(open(os.path.join(ON, "sotto_worker.py"), "rb").read())
    print("on   worker   %d B  sha256 %s  (copy of live: %s)"
          % (len(live_bytes), on_sha, on_sha == live_sha))
    if on_sha != live_sha:
        problems.append("the ON copy is not byte-identical to the live worker")

    for name in SUPPORT:
        src = os.path.join(WORKER, name)
        if not os.path.exists(src):
            problems.append("support module missing at %s" % src)
            continue
        src_sha = sha(open(src, "rb").read())
        for dst_dir, label in ((OFF, "off"), (ON, "on")):
            dst = os.path.join(dst_dir, name)
            shutil.copyfile(src, dst)
            got = sha(open(dst, "rb").read())
            if got != src_sha:
                problems.append("%s/%s copy mismatch" % (label, name))
        print("support       %-22s %s" % (name, src_sha[:16]))

    cfg = json.load(open(LIVE_CONFIG, encoding="utf-8"))
    if "use_denoise" not in cfg:
        problems.append("the live config lost the use_denoise key")
    false_cfg = dict(cfg)
    false_cfg["use_denoise"] = False
    true_cfg = dict(cfg)
    true_cfg["use_denoise"] = True
    for name, obj, want in (("config-false.json", false_cfg, False),
                            ("config-true.json", true_cfg, True)):
        path = os.path.join(FROZEN, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        back = json.load(open(path, encoding="utf-8"))
        if back.get("use_denoise") is not want:
            problems.append("%s did not round-trip use_denoise=%r" % (name, want))
        print("config        %-22s use_denoise=%s  %d B  sha256 %s"
              % (name, back.get("use_denoise"), os.path.getsize(path), sha(open(path, "rb").read())))
    # The pair must differ in EXACTLY one key, or the A/B is not one variable.
    diff = [k for k in set(false_cfg) | set(true_cfg) if false_cfg.get(k) != true_cfg.get(k)]
    print("keys differing between the two configs : %s" % (diff,))
    if diff != ["use_denoise"]:
        problems.append("configs differ in more than use_denoise: %s" % diff)

    if problems:
        for p in problems:
            print("SETUP-REFUSED: %s" % p)
        print("VERDICT FAIL")
        return 1
    print("VERDICT PASS -- three arms staged; A vs B differ in one file, B vs C in one key")
    return 0


if __name__ == "__main__":
    sys.exit(main())
