"""REDUX LIVE OVERLAY ORACLE (lane S3) -- in process, launches NOTHING.

PROVES BOTH COLOURS OF THE GUARD THAT PUTS THE REDUX PASS *POR CIMA* OF EVERY
LIVE LINE.

  ARM A  Redux ON    the live final is HELD, and exactly ONE line per segment is
                     published -- the Redux text, stamped producer="redux".
  ARM B  Redux OFF   the live final is published UNCHANGED (nemotron's text, no
                     producer), and the canonical transcript stays EMPTY. That is
                     the honest OFF colour, and it is what the run did before
                     this lane existed.
  NEG    the guard REMOVED from an in-memory copy of the SHIPPED function: the
                     live line is published TOO, so one segment produces TWO
                     finals and nemotron's text reaches the panel. The oracle
                     MUST go RED here, or it cannot say NO.

THE FUNCTION UNDER TEST IS NOT RE-TYPED. publish_captions is extracted from
worker/sotto_worker.py with ast, byte for byte, and exec'd. A re-typed copy
would prove only that the oracle agrees with itself. The neg-arm mutates the
EXTRACTED STRING in memory -- the shipped file is never written.

THE PANEL HALF runs the REAL app/panel/caption-formulation.js and
history-source.js under node, so "which line the history takes" is decided by
the shipped gate, not by this file.
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
REDUX_LIVE = os.path.join(ROOT, "worker", "redux_live.py")
PANEL_ORACLE = os.path.join(HERE, "redux-live-overlay-panel-oracle.js")

NEMOTRON = "o nemotron ouviu esta frase ao vivo"
REDUX = "o parakeet redux ouviu esta frase melhor"
SOURCE = "proc:4242"
START = 0.0
END = 3.0


def load_module(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_publish_captions(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "publish_captions":
            seg = ast.get_source_segment(source, node)
            if not seg:
                break
            return seg, node
    raise SystemExit("FATAL: publish_captions NOT FOUND in " + WORKER)


def neuter_guard(fn_src):
    """Keep the guard's CALL, drop its SKIP. Returns (source, span).

    The mutant replaces the `continue` inside the hold_live_final guard with
    `pass`: the overlay is STILL handed the segment (so the Redux pass still
    runs) but the live line is no longer withheld -- the invariant under test,
    isolated from everything else. Blanking the whole `if` would ALSO stop
    feeding the overlay, and a mutant that breaks two things at once proves
    neither of them.
    """
    tree = ast.parse(fn_src)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            seg = ast.get_source_segment(fn_src, node.test) or ""
            if "hold_live_final" in seg:
                target = node
                break
    if target is None:
        raise SystemExit("NEG-ARM: could not find the hold_live_final guard")
    lines = fn_src.split(chr(10))
    span = []
    for stmt in target.body:
        if isinstance(stmt, ast.Continue):
            i = stmt.lineno - 1
            indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            lines[i] = indent + "pass"
            span.append(stmt.lineno)
    if not span:
        raise SystemExit("NEG-ARM: the guard has no `continue` to neuter")
    return chr(10).join(lines), span


class FakeBackend:
    """The overlay's backend contract: .name and .transcribe(pcm) -> (text, segs)."""

    def __init__(self, text, latency_s=0.05, fail=False):
        self.name = "parakeet-redux-fake"
        self.text = text
        self.latency_s = latency_s
        self.fail = fail
        self.calls = 0

    def transcribe(self, pcm):
        self.calls += 1
        if self.latency_s:
            time.sleep(self.latency_s)
        if self.fail:
            raise RuntimeError("fake backend failure")
        return self.text, []


def norm(s):
    """The panel FORMULATES a line: first letter up, sentence period on.

    That is caption-formulation.js's own long-standing behaviour and this lane
    does not change it, so the comparison strips case and the closing period
    instead of pinning the panel's typography as if it were the contract.
    """
    return " ".join((s or "").lower().rstrip(".").split())


def live_final():
    return {"type": "caption", "text": NEMOTRON, "start": START, "end": END,
            "final": True, "source": SOURCE}


def run_arm(fn_src, overlay, wait_s=10.0):
    """Drive the SHIPPED publish_captions and collect what it published."""
    emitted = []
    counters = {"captions": 0, "redux_live_captions": 0}

    def emit(**payload):
        emitted.append(payload)

    asr = type("Asr", (), {"name": "nemotron-fake"})()
    ns = {"counters": counters, "emit": emit, "overlay": overlay, "asr": asr}
    exec(fn_src, ns)
    publish = ns["publish_captions"]

    publish([live_final()])
    first = [dict(e) for e in emitted]

    if overlay is not None and wait_s:
        deadline = time.time() + wait_s
        while time.time() < deadline:
            done = (overlay.redux_lines + overlay.fallbacks
                    + overlay.failures + overlay.expired)
            if done:
                break
            time.sleep(0.02)
        publish([])

    return {"first": first, "all": [dict(e) for e in emitted],
            "counters": dict(counters)}


class Args:
    """Just the attributes redux_live_settings reads, all at their CLI defaults."""

    def __init__(self, **kw):
        self.redux_live = kw.get("redux_live", False)
        self.redux_live_engine = kw.get("redux_live_engine")
        self.redux_live_keep = kw.get("redux_live_keep", 0.0)
        self.redux_live_min_audio = kw.get("redux_live_min_audio", 0.0)
        self.redux_live_deadline = kw.get("redux_live_deadline", 0.0)
        self.redux_live_threads = kw.get("redux_live_threads", 0)


def extract_function(source, name):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            seg = ast.get_source_segment(source, node)
            if seg:
                return seg, node
    raise SystemExit("FATAL: %s NOT FOUND" % name)


def neuter_config_rung(fn_src):
    """Make the CONFIG rung read NOTHING, leaving the flag and env rungs intact.

    Selective on purpose: a mutant that also broke the flag or the env rung
    would go red everywhere and prove nothing about the config.
    """
    old = 'bool(rl.get("enabled", False))'
    if len(fn_src.split(old)) - 1 != 1:
        raise SystemExit("NEG-ARM(settings): the config rung anchor moved")
    return fn_src.replace(old, "False")


# label, args kwargs, cfg, env, expected tuple, required-to-go-red-on-the-mutant
SETTINGS_CASES = [
    ("no rung set at all -> OFF",
     {}, {}, {}, (False, "config", "onnx", 90.0, 1.0, 4.0, 2), False),
    ("CONFIG enables it",
     {}, {"enabled": True}, {}, (True, "config", "onnx", 90.0, 1.0, 4.0, 2), True),
    ("env=1 beats a config that says OFF",
     {}, {"enabled": False}, {"SOTTO_REDUX_LIVE": "1"},
     (True, "env", "onnx", 90.0, 1.0, 4.0, 2), False),
    ("env=0 is an EXPLICIT OFF that beats a config that says ON",
     {}, {"enabled": True}, {"SOTTO_REDUX_LIVE": "0"},
     (False, "env", "onnx", 90.0, 1.0, 4.0, 2), False),
    ("the FLAG beats env=0 and a config that says OFF",
     {"redux_live": True}, {"enabled": False}, {"SOTTO_REDUX_LIVE": "0"},
     (True, "flag", "onnx", 90.0, 1.0, 4.0, 2), False),
    ("EVERY KNOB comes from the config",
     {}, {"enabled": True, "engine": "ternary", "keep_s": 12.5,
          "min_audio_s": 0.5, "deadline_s": 9.0, "threads": 7}, {},
     (True, "config", "ternary", 12.5, 0.5, 9.0, 7), True),
    ("EVERY KNOB loses to the flag",
     {"redux_live": True, "redux_live_engine": "onnx", "redux_live_keep": 3.0,
      "redux_live_min_audio": 0.25, "redux_live_deadline": 2.0,
      "redux_live_threads": 1},
     {"engine": "ternary", "keep_s": 12.5, "min_audio_s": 0.5,
      "deadline_s": 9.0, "threads": 7}, {},
     (True, "flag", "onnx", 3.0, 0.25, 2.0, 1), False),
]


def settings_arms(worker_src):
    """Prove the config rung is READ, using the SHIPPED function, not a copy."""
    fn_src, _node = extract_function(worker_src, "redux_live_settings")
    ns = {"os": os}
    for _const in ("REDUX_LIVE_ENGINE_DEFAULT", "REDUX_LIVE_KEEP_S",
                   "REDUX_LIVE_MIN_AUDIO_S", "REDUX_LIVE_DEADLINE_S",
                   "REDUX_LIVE_THREADS"):
        _m = re.search(r"^%s\s*=\s*(.+)$" % _const, worker_src, re.M)
        if not _m:
            raise SystemExit("FATAL: constant %s not found" % _const)
        ns[_const] = ast.literal_eval(_m.group(1).strip())
    exec(fn_src, ns)
    resolve = ns["redux_live_settings"]

    def run(src):
        n = {"os": os}
        n.update({k: v for k, v in ns.items() if k.startswith("REDUX_LIVE_")})
        exec(src, n)
        fn = n["redux_live_settings"]
        out = []
        for label, akw, cfg, env, expected, req in SETTINGS_CASES:
            got = list(fn(Args(**akw), {"redux_live": cfg}, env))
            out.append({"label": label, "expected": list(expected), "got": got,
                        "ok": got == list(expected), "required_red": req})
        return out, fn

    cases, _ = run(fn_src)

    # The SHIPPED worker/config.json, read from disk: proves the block parses
    # and that the rung is consulted at all. Case 6 above is the load-bearing
    # one for "the knobs are READ", because these values ARE the built-ins.
    with open(os.path.join(ROOT, "worker", "config.json"), encoding="utf-8") as fh:
        shipped = json.load(fh)
    shipped_has_block = isinstance(shipped.get("redux_live"), dict)
    shipped_got = list(resolve(Args(), shipped, {}))
    shipped_expected = [False, "config", "onnx", 90.0, 1.0, 4.0, 2]
    # The shipped knobs equal the built-ins, so the case above cannot tell a
    # READ block from a block that was ignored. Flipping the shipped block's own
    # `enabled` can: if the answer moves, the block is what is being read.
    flipped = dict(shipped)
    flipped["redux_live"] = dict(shipped["redux_live"], enabled=True)
    shipped_flipped_got = list(resolve(Args(), flipped, {}))
    shipped_flipped_expected = [True, "config", "onnx", 90.0, 1.0, 4.0, 2]

    mutant = neuter_config_rung(fn_src)
    neg_cases, _ = run(mutant)

    neg_flipped = list(run(mutant)[1](Args(), flipped, {}))
    return {"cases": cases, "shipped_has_block": shipped_has_block,
            "shipped_got": shipped_got, "shipped_expected": shipped_expected,
            "shipped_flipped_got": shipped_flipped_got,
            "shipped_flipped_expected": shipped_flipped_expected,
            "shipped_flipped_ok": shipped_flipped_got == shipped_flipped_expected,
            "neg_flipped": neg_flipped,
            "shipped_ok": (shipped_has_block and shipped_got == shipped_expected
                           and shipped_flipped_got == shipped_flipped_expected),
            "neg_cases": neg_cases,
            "neg_required_all_red": all(not c["ok"] for c in neg_cases if c["required_red"]),
            "neg_others_still_green": all(c["ok"] for c in neg_cases if not c["required_red"])}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--neg-arm", action="store_true",
                    help="also run the guard-removed copy and require it RED")
    args = ap.parse_args()

    with open(WORKER, "r", encoding="utf-8") as fh:
        worker_src = fh.read()
    fn_src, node = extract_publish_captions(worker_src)
    print("publish_captions extracted from %s lines %d..%d (%d chars)"
          % (os.path.basename(WORKER), node.lineno, node.end_lineno, len(fn_src)))

    rl = load_module(REDUX_LIVE, "redux_live_oracle_target")
    import numpy as np

    def fresh_overlay():
        ov = rl.ReduxLiveOverlay(
            FakeBackend(REDUX),
            producer_model="parakeet-redux-fake",
            log=lambda m: None,
            keep_s=30.0, silence_s=0.5, deadline_s=5.0,
            max_queue=6, tick_s=0.01, armed=True,
        )
        ov.start()
        pcm = np.zeros(int(4.0 * ov.sr), dtype=np.float32)
        ov.accept(pcm)
        return ov

    arms = {}

    ov_a = fresh_overlay()
    arms["A_redux_on"] = run_arm(fn_src, ov_a)
    ov_a.stop()

    arms["B_redux_off"] = run_arm(fn_src, None)

    neg_src, span = neuter_guard(fn_src)
    print("neg-arm: neutered the guard's continue at line(s) %s" % span)
    ov_c = fresh_overlay()
    arms["NEG_guard_removed"] = run_arm(neg_src, ov_c)
    ov_c.stop()

    settings = settings_arms(worker_src)

    # ── the panel half: the REAL modules decide what the history takes ────────
    payload = {"nemotron": NEMOTRON, "redux": REDUX, "source": SOURCE,
               "start": START, "arms": []}
    for name, res in arms.items():
        payload["arms"].append({"name": name, "events": res["all"]})
    arms_json = os.path.join(os.environ.get("TMPDIR") or HERE, "redux-live-overlay-arms.json")
    with open(arms_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)

    panel = {}
    try:
        proc = subprocess.run(
            ["node", PANEL_ORACLE, arms_json],
            capture_output=True, text=True, timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            print("PANEL ORACLE rc=%d" % proc.returncode)
            print(proc.stdout[-4000:])
            print(proc.stderr[-4000:])
            panel = {"error": "panel oracle rc=%d" % proc.returncode}
        else:
            panel = json.loads(proc.stdout)
    except Exception as exc:
        panel = {"error": "%s: %s" % (type(exc).__name__, exc)}

    # ── verdict ──────────────────────────────────────────────────────────────
    #
    # ARM A and ARM B are POSITIVE claims about the shipped function. The NEG
    # arm is the SAME arm-A predicates applied to the neutered copy, and each
    # one is REQUIRED TO BE FALSE there. That is what makes this a control and
    # not a second green: if the guard were inert, arm A would behave exactly
    # like the mutant, its own predicates would fail, and the gate would go RED
    # on the positive side. A gate that cannot say NO is not a gate.
    checks = []

    def chk(arm, label, ok, detail):
        checks.append({"arm": arm, "label": label, "ok": bool(ok), "detail": detail})

    def caps(arm_name):
        return [e for e in arms[arm_name]["all"] if e.get("type") == "caption"]

    def texts(arm_name):
        return [e.get("text") for e in caps(arm_name)]

    def panel_of(arm_name):
        return (panel.get("arms") or {}).get(arm_name) or {}

    def arm_a_predicates(arm_name):
        """The six claims the REDUX-ON arm makes about one segment."""
        c = caps(arm_name)
        p = panel_of(arm_name)
        stream = arms[arm_name]["all"]
        canon = p.get("canonical") or []
        return [
            # ── STREAM-level claims: these ARE what the guard protects, so the
            #    neg-arm REQUIRES each of them to go FALSE on the neutered copy.
            ("exactly ONE final per segment",
             len(c) == 1, "published=%d" % len(c), True),
            ("the published text IS the Redux text",
             len(c) == 1 and c[0].get("text") == REDUX,
             json.dumps(texts(arm_name), ensure_ascii=False), True),
            ("the event DECLARES its producer",
             len(c) == 1 and c[0].get("producer") == "redux",
             json.dumps(sorted((c[0] if c else {}).keys())), True),
            ("nemotron's text NEVER reaches the stream",
             not any(norm(e.get("text")) == norm(NEMOTRON) for e in stream),
             "stream=%d" % len(stream), True),
            # ── END-STATE claims: reported, NOT required to go red. MEASURED:
            #    they survive the neutered guard, because the panel replaces a
            #    row IN PLACE and the later Redux event wins the same identity.
            #    Claiming these as the control would be a gate that cannot say
            #    NO; hiding them would be a gate that oversells itself.
            ("the PANEL row shows the Redux text",
             norm(p.get("row_text")) == norm(REDUX),
             json.dumps(p.get("row_text"), ensure_ascii=False), False),
            ("the HISTORY takes the Redux line (canonical)",
             len(canon) == 1 and norm((canon[0] or {}).get("line")) == norm(REDUX),
             json.dumps(canon, ensure_ascii=False)[:220], False),
        ]

    for label, ok, detail, _req in arm_a_predicates("A_redux_on"):
        chk("A", label, ok, detail)

    b = caps("B_redux_off")
    pb = panel_of("B_redux_off")
    chk("B", "exactly ONE final per segment", len(b) == 1, "published=%d" % len(b))
    chk("B", "the text stays NEMOTRON's",
        len(b) == 1 and b[0].get("text") == NEMOTRON,
        json.dumps(texts("B_redux_off"), ensure_ascii=False))
    chk("B", "NO producer is invented",
        len(b) == 1 and "producer" not in b[0],
        json.dumps(sorted((b[0] if b else {}).keys())))
    chk("B", "the PANEL row shows nemotron's text",
        norm(pb.get("row_text")) == norm(NEMOTRON),
        json.dumps(pb.get("row_text"), ensure_ascii=False))
    chk("B", "the HISTORY takes NOTHING (the honest OFF colour)",
        len(pb.get("canonical") or []) == 0,
        json.dumps(pb.get("canonical"), ensure_ascii=False)[:220])

    for c in settings["cases"]:
        chk("D", "settings: " + c["label"], c["ok"],
            "got=%s expected=%s" % (c["got"], c["expected"]))
    chk("D", "settings: the SHIPPED worker/config.json is READ", settings["shipped_ok"],
        "has_block=%s got=%s flipped_got=%s" % (settings["shipped_has_block"],
                                              settings["shipped_got"],
                                              settings["shipped_flipped_got"]))

    observations = []
    if args.neg_arm:
        for c in settings["neg_cases"]:
            if c["required_red"]:
                chk("NEG", "settings: " + c["label"] + "   [REQUIRED RED]", not c["ok"],
                    "mutant got=%s" % (c["got"],))
        chk("NEG", "settings: the shipped config block read   [REQUIRED RED]",
            settings["neg_flipped"] != settings["shipped_flipped_expected"],
            "mutant got=%s" % (settings["neg_flipped"],))
        chk("NEG", "settings: the mutant is SELECTIVE (flag/env rungs untouched)",
            settings["neg_others_still_green"],
            "non-config cases still green=%s" % settings["neg_others_still_green"])
        for label, ok, detail, required in arm_a_predicates("NEG_guard_removed"):
            if required:
                chk("NEG", label + "   [REQUIRED RED]", not ok,
                    "mutant made it FALSE -> " + detail if not ok
                    else "STILL TRUE on the mutant -> the guard is not load-bearing here")
            else:
                observations.append({"label": label, "held_on_mutant": bool(ok),
                                     "detail": detail})
    else:
        chk("NEG", "neg-arm not requested (--neg-arm)", False, "not run")

    print("")
    for c in checks:
        print("  [%s] %-3s %s\n         -- %s"
              % ("ok" if c["ok"] else "XX", c["arm"], c["label"], c["detail"]))

    pos = [c for c in checks if c["arm"] in ("A", "B")]
    neg = [c for c in checks if c["arm"] == "NEG"]
    verdict = "PASS" if (checks and all(c["ok"] for c in checks)) else "FAIL"
    print("")
    print("VERDICT: %s" % verdict)
    print("  positive arms A/B : %d/%d green" % (sum(1 for c in pos if c["ok"]), len(pos)))
    if args.neg_arm:
        print("  NEG (stream claims on the neutered copy): %d/%d went RED as required"
              % (sum(1 for c in neg if c["ok"]), len(neg)))
        for o in observations:
            print("  NEG [not required to move] %s -> held_on_mutant=%s"
                  % (o["label"], o["held_on_mutant"]))
    else:
        print("  NEG: NOT RUN -- this run cannot say NO")
    report = {"verdict": verdict, "checks": checks, "arms": arms,
              "neg_observations": observations,
              "panel": panel, "neg_arm": bool(args.neg_arm),
              "worker": {"path": WORKER, "publish_captions_lines": [node.lineno, node.end_lineno]}}
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
        print("report -> " + args.out)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
