import argparse, importlib.util, json, os, shutil, sys, tempfile, time, traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
Q = chr(34)
NL = chr(10)

def load_pool(worker_dir):
    # Import model_vram_pool + vram_residency from a directory.
    sys.path.insert(0, worker_dir)
    import model_vram_pool as pool
    import vram_residency as res
    return pool, res

def load_pool_from(path):
    # Import a pool file under a distinct module name (the negative arm).
    name = "model_vram_pool_mutant"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

def make_mutant(pool, res, tmpdir):
    # Write a COPY of the pool with the reuse guards removed.
    #
    # The pool shares an entry in TWO places: the fast path at the top of
    # get_or_load, and the race path at its end. A mutant that disables only the
    # first still shares on the second call (measured: the negative arm went GREEN
    # when only one was removed), so BOTH are disabled here. Everything else - the
    # key, the loader, the VRAM measurement, the foreign verdict - is
    # byte-identical, so a RED is attributable to the sharing and nothing else.
    src = open(pool.__file__, "rb").read().decode("utf-8")
    fast = NL.join(["        if entry is not None:",
                    "            entry.refs += 1",
                    "            return entry"])
    race = NL.join(["        if entry is not None:          # raced: someone loaded it meanwhile",
                    "            entry.refs += 1",
            "            _discard(load)",
                    "            return entry"])
    if fast not in src or race not in src:
        raise SystemExit("MUTANT FAILED: a reuse guard was not found verbatim; "
                         "the negative arm would not be testing what it claims")
    mutant = src.replace(fast, NL.join(["        if False:",
                                       "            entry.refs += 1",
                                       "            return entry"]), 1)
    mutant = mutant.replace(race, NL.join(["        if False:                    # raced: someone loaded it meanwhile",
                                           "            entry.refs += 1",
                                           "            _discard(load)",
                                           "            return entry"]), 1)
    mdir = os.path.join(tmpdir, "mutant")
    os.makedirs(mdir, exist_ok=True)
    shutil.copyfile(res.__file__, os.path.join(mdir, "vram_residency.py"))
    out = os.path.join(mdir, "model_vram_pool.py")
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(mutant)
    return out

class C:
    # One check: name, status, detail.
    def __init__(self, name):
        self.name = name
        self.status = "PASS"
        self.detail = ""

    def fail(self, detail):
        if self.status == "PASS":
            self.status = "FAIL"
        self.detail = (self.detail + " " + detail).strip()

    def skip(self, detail):
        if self.status == "PASS":
            self.status = "SKIP"
        self.detail = (self.detail + " " + detail).strip()


def run_checks(pool, res, model_dir, loader, mine, results):
    # Run the check suite against a pool module (real or mutant).
    own = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    tag = results.get("tag", "")
    c1 = C(tag + "CHK-1 same model returns the SAME entry")
    c2 = C(tag + "CHK-2 the second call adds ZERO VRAM")
    c3 = C(tag + "CHK-3 pool holds ONE entry with refs=2")
    c4 = C(tag + "CHK-4 a different model dir is a different entry")
    c5 = C(tag + "CHK-5 a resident model in another process is DETECTED")
    c6 = C(tag + "CHK-6 foreign_policy=refuse refuses instead of duplicating")
    c7 = C(tag + "CHK-7 the verdict is observable in the log")
    results["checks"] = [c1, c2, c3, c4, c5, c6, c7]

    # CHK-1/2/3: the core guarantee.
    try:
        v0 = pool._vram_mine()
        e1 = pool.get_or_load(model_dir, providers=own, loader=loader)
        v1 = pool._vram_mine()
        e2 = pool.get_or_load(model_dir, providers=own, loader=loader)
        v2 = pool._vram_mine()
        c1.detail = ("first=%d second=%d identical=%s vram %.1f -> %.1f -> %.1f MiB"
                     % (id(e1), id(e2), e1 is e2, v0 or -1, v1 or -1, v2 or -1))
        if e1 is not e2:
            c1.fail("the second get_or_load built a SECOND entry")
        if e2.refs < 2:
            c1.fail("refs=%d, expected >= 2 (the pool is not sharing)" % e2.refs)

        delta = None if (v1 is None or v2 is None) else round(v2 - v1, 1)
        c2.detail = ("dedicated VRAM before second call %.1f MiB, after %.1f MiB, delta %s MiB"
                     % (v1 if v1 is not None else -1, v2 if v2 is not None else -1, delta))
        if delta is None:
            c2.skip("VRAM unmeasurable in this process")
        elif abs(delta) > 1.0:
            c2.fail("the second call moved %.1f MiB - a second copy was built" % delta)

        st = pool.pool_state()
        c3.detail = ("pool entries=%d refs=%s" % (st["count"], e2.refs))
        if st["count"] != 1:
            c3.fail("pool holds %d entries for ONE model asked twice" % st["count"])
        if e2.refs != 2:
            c3.fail("refs=%d, expected 2" % e2.refs)
    except Exception:
        msg = traceback.format_exc(limit=2).splitlines()[-1]
        for c in (c1, c2, c3):
            c.fail("exception: " + msg)

    # CHK-4: the key discriminates.
    try:
        missing = os.path.join(tempfile.gettempdir(), "s8-no-such-model-dir")
        k_same = pool.pool_key(model_dir, providers=own, loader=loader)
        k_diff_dir = pool.pool_key(missing, providers=own, loader=loader)
        k_diff_prov = pool.pool_key(model_dir, providers=["CPUExecutionProvider"], loader=loader)
        c4.detail = ("diff_dir=%s diff_providers=%s"
                     % (k_same != k_diff_dir, k_same != k_diff_prov))
        if k_same == k_diff_dir:
            c4.fail("two different model dirs produced the same pool key")
        if k_same == k_diff_prov:
            c4.fail("two provider lists produced the same pool key")
    except Exception:
        c4.fail("exception: " + traceback.format_exc(limit=2).splitlines()[-1])

    # CHK-5: the resident-model verdict (synthetic + live).
    try:
        ident = res.model_identity(model_dir, hash_weights=False)
        synth = [{"pid": 424242, "name": "python.exe",
                  "cmdline": "python.EXE H:" + chr(92) + "sotto" + chr(92) + "worker" + chr(92) + "sotto_worker.py",
                  "ded_MiB": 2027.5, "tot_MiB": 2105.5}]
        strong = res.find_model_holders(ident, synth, own_pid=mine)
        c5.detail = ("synthetic holder found=%d tier=%s"
                     % (len(strong), strong[0].get("tier") if strong else None))
        if len(strong) != 1:
            c5.fail("a process running sotto_worker.py was not recognised")
        live = res.find_model_holders(ident, res.per_process_vram(min_mib=0.5), own_pid=mine)
        c5.detail += (" | live sotto holders=%d" % len(live))
        if not live:
            c5.skip("no Sotto worker resident on this box right now")
        else:
            c5.detail += (" pid=%s ded=%.1f MiB" % (live[0].get("pid"), live[0].get("ded_MiB")))
    except Exception:
        c5.fail("exception: " + traceback.format_exc(limit=2).splitlines()[-1])

    # CHK-6: the refusal path. It must use a key that is NOT already in the pool,
    # otherwise the early return fires first and the arm proves nothing.
    try:
        pool.register_loader("noop-refusal-arm")(
            lambda *a, **k: {"sessions": {}, "model": None, "processor": None})
        ident6 = res.model_identity(model_dir, hash_weights=False)
        synth6 = [{"pid": 424242, "name": "python.exe",
                   "cmdline": "python.EXE H:" + chr(92) + "sotto" + chr(92) + "worker" + chr(92) + "sotto_worker.py",
                   "ded_MiB": 2027.5, "tot_MiB": 2105.5}]
        pool._foreign_verdict = lambda identity: synth6
        raised = "NOTHING"
        try:
            pool.get_or_load(model_dir, providers=own, loader="noop-refusal-arm",
                             foreign_policy="refuse")
        except pool.ResidentModelError:
            raised = "ResidentModelError"
        except Exception as exc:
            raised = type(exc).__name__
        c6.detail = "foreign_policy=refuse raised " + raised
        if raised != "ResidentModelError":
            c6.fail("expected ResidentModelError, got " + raised)
    except Exception:
        c6.fail("exception: " + traceback.format_exc(limit=2).splitlines()[-1])

    # CHK-7: the verdict is in the log.
    try:
        lines = pool.verdict_lines(model_dir)
        text = NL.join(lines)
        c7.detail = ("%d lines; says ALREADY RESIDENT: %s"
                     % (len(lines), "ALREADY RESIDENT" in text))
        if "ALREADY RESIDENT" not in text:
            c7.fail("the verdict does not say the model is already resident")
    except Exception:
        c7.fail("exception: " + traceback.format_exc(limit=2).splitlines()[-1])
    return results["checks"]

def main():
    ap = argparse.ArgumentParser(description="VRAM reuse oracle (in-process, launches nothing)")
    ap.add_argument("--worker-dir", default=os.path.normpath(os.path.join(_HERE, os.pardir, "worker")))
    ap.add_argument("--model-dir", default=None)
    ap.add_argument("--loader", default="onnx-single",
                    help="onnx-single = one real ORT session; sotto = full engine; noop = no GPU")
    ap.add_argument("--neg-arm", action="store_true",
                    help="run the negative arm: the pool copy with the reuse guard removed")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    worker_dir = os.path.abspath(args.worker_dir)
    if not os.path.isfile(os.path.join(worker_dir, "model_vram_pool.py")):
        raise SystemExit("model_vram_pool.py not found in " + worker_dir)
    model_dir = args.model_dir
    if model_dir is None:
        try:
            cfg = json.load(open(os.path.join(worker_dir, "config.json"), encoding="utf-8"))
            model_dir = os.path.normpath(os.path.join(worker_dir, cfg["model"]["dir"]))
        except Exception:
            model_dir = worker_dir
    model_dir = os.path.normpath(model_dir)
    if not os.path.isdir(model_dir):
        raise SystemExit("model dir not found: " + model_dir)

    pool, res = load_pool(worker_dir)
    mine = os.getpid()

    print("VRAM-REUSE-ORACLE")
    print("  worker dir : %s" % worker_dir)
    print("  model dir  : %s" % model_dir)
    print("  loader     : %s" % args.loader)
    print("  pid        : %d" % mine)
    print("")

    print("== GREEN ARM (the pool as shipped) ==")
    green = {"tag": "[green] "}
    gchecks = run_checks(pool, res, model_dir, args.loader, mine, green)
    for c in gchecks:
        print("  %-6s %s" % (c.status, c.name))
        if c.detail:
            print("         %s" % c.detail)
    print("")
    print("  -- who holds GPU memory right now --")
    for line in res.vram_brief(model_dir, own_pid=mine):
        print("  " + line)
    print("")

    nchecks = []
    if args.neg_arm:
        tmp = tempfile.mkdtemp(prefix="vram-reuse-neg-")
        try:
            mpath = make_mutant(pool, res, tmp)
            mpool = load_pool_from(mpath)
            print("== NEGATIVE ARM (reuse guards removed in a COPY) ==")
            neg = {"tag": "[neg] "}
            nchecks = run_checks(mpool, res, model_dir, args.loader, mine, neg)
            for c in nchecks:
                print("  %-6s %s" % (c.status, c.name))
                if c.detail:
                    print("         %s" % c.detail)
            print("")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def is_core(c):
        # The arm tag is a PREFIX of the name, so match on containment.
        return any(s in c.name for s in ("CHK-1", "CHK-2", "CHK-3", "CHK-4"))

    def is_red_core(c):
        return any(s in c.name for s in ("CHK-1", "CHK-2", "CHK-3"))

    core = [c for c in gchecks if is_core(c)]
    if not core:
        raise SystemExit("internal error: no green core checks were recorded")
    green_ok = all(c.status == "PASS" for c in core)
    green_fail = [c.name for c in gchecks if c.status == "FAIL"]

    print("== VERDICT ==")
    print("  green arm (real pool): %s" % ("PASS" if green_ok else "FAIL " + str(green_fail)))
    ok = green_ok
    if nchecks:
        ncore = [c for c in nchecks if is_red_core(c)]
        nred = [c.name for c in ncore if c.status == "FAIL"]
        print("  neg arm  (guards removed): %d of %d core checks RED -> %s"
              % (len(nred), len(ncore), "RED (as expected)" if nred else "NOT RED (BAD)"))
        if not nred:
            ok = False
    print("  VERDICT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())