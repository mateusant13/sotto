#!/usr/bin/env python
"""ORACLE: THE PLUMBING -- `--speakers` OFF MUST BE THE OLD CODE, EVENT FOR EVENT.

This is the gate on the only edit made to `worker/sotto_worker.py` in this
change: 89 insertions and 1 alteration, in a 6 802-line CRLF file that is the
most sensitive thing in the product. A caption engine that changes what it
emits while nobody asked it to is not a feature, it is an incident, and the
owner is the one who finds out.

SO THE TEST IS DIFFERENTIAL, NOT A LIST OF KEYS. It extracts `LineFormer` from
**two** revisions of the worker -- the one in `HEAD`, before this change, and
the working tree after it -- feeds both the identical scenario, and requires the
events to be EQUAL. Not "has the same keys": equal. Same text, same floats,
same `final`, same `closed`, same `chunks`, same nothing-extra.

`LineFormer` is extracted by AST rather than imported, and that is deliberate:
`worker/sotto_worker.py` is 358 KB and pulls the ASR stack in. The class needs
four module-level names and nothing else (`LINE_TERMINAL`, `SENTENCE_GAP_S`,
`SENTENCE_MAX_CHARS`, `join_fragments`), so the gate runs in milliseconds and
loads no model.

THE ARMS:

    off            no provider -> events equal to the pre-change revision
    no payload     a provider returning None -> still equal
    stale payload  a payload older than the window -> still equal
    crash          a provider that RAISES -> still equal, the caption survives
    no source      a former with no device -> not one key added
    on             a fresh payload -> `speaker` stamped, `source` per voice
    unowned        a line nobody holds -> `speaker: None`, device kept
    the flag       exists, and is OFF unless asked for
    the import     `speaker_bridge` is NOT imported at module level

THE NEGATIVE ARM breaks the plumbing five ways. Four of them are the mistake
this gate exists to catch: turning attribution on for everybody.
"""
from __future__ import annotations

import ast
import builtins
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = r"H:\sotto"
WORKER = os.path.join(REPO, "worker", "sotto_worker.py")
BRIDGE = os.path.join(REPO, "worker", "speaker_bridge.py")
SIDE = os.path.join(REPO, "worker", "speaker_sidecar.py")
FIXTURE = os.path.join(REPO, "_main", "_hoje-ctrl.json")

EXIT_PASS, EXIT_FAIL = 0, 1

SOURCE = "device:CABLE Output (VB-Audio Virtual Cable)"

#: A mini-call: two people, one pause. The pause is what closes the first line,
#: so the scenario exercises the partial, the close and the out-of-band final.
SCENARIO = [
    ("e eu quero que o alt c", 0.00, 0.40, True),
    ("mostre as transcricoes", 0.40, 0.80, False),
    ("em tempo real", 1.20, 1.60, False),
    ("e ai pessoal tudo bem", 1.60, 2.00, False),
    ("sim tudo certo", 2.00, 2.40, False),
]


def _free_names(node) -> set:
    """Names a node reads but does not bind. Over-approximated on purpose.

    Over-approximating only ever pulls in one more module-level definition; a
    local read before assignment would be counted as free. That is the safe
    direction -- the closure below only adds definitions that actually exist.
    """
    bound = set()
    used = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            (bound if isinstance(sub.ctx, (ast.Store, ast.Del)) else used).add(sub.id)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(sub.name)
        elif isinstance(sub, ast.arg):
            bound.add(sub.arg)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            bound.add(sub.name)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            for a in sub.names:
                bound.add((a.asname or a.name).split(".")[0])
    return used - bound - set(dir(builtins))


def extract_lineformer(source: str):
    """Compile `LineFormer` plus the transitive closure of what it needs.

    NOT imported, and that is the point: `worker/sotto_worker.py` is 358 KB and
    drags the ASR stack in behind it. The gate runs in milliseconds and loads
    no model, no ONNX session and no audio device -- which is also the only way
    this test is allowed to run while the owner is on a call.

    The closure is transitive because a helper's DEFAULT ARGUMENT is evaluated
    when its `def` executes. `PLP_MODE_INCLUDE_TARGET_PROCESS_TREE` is one, and
    including the whole module blindly raised `NameError` on an unrelated
    function that `LineFormer` never calls.
    """
    tree = ast.parse(source)
    defs = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defs[node.name] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defs[t.id] = node

    chosen = {"LineFormer": defs["LineFormer"]}
    need = set(_free_names(defs["LineFormer"]))
    changed = True
    while changed:
        changed = False
        for name in sorted(need):
            if name in chosen or name not in defs:
                continue
            chosen[name] = defs[name]
            need |= _free_names(defs[name])
            changed = True

    body = [ast.ImportFrom(module="__future__", names=[ast.alias("annotations")],
                           level=0)]
    body.extend(chosen[n] for n in sorted(chosen) if n != "LineFormer")
    body.append(chosen["LineFormer"])
    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {}
    exec(compile(mod, "<extracted-LineFormer>", "exec"), ns)   # noqa: S102
    return ns["LineFormer"]


def run_scenario(former_cls, source=SOURCE, provider=None):
    """Feed the scenario to a former and return every event it produced."""
    former = former_cls(min_chars=3, emit_partial=True, source=source)
    if provider is not None:
        former.set_speaker_provider(provider)
    events = []
    for text, start, end, cont in SCENARIO:
        events.extend(former.push(text, start, end, cont))
    events.extend(former.flush())
    events.extend(former.take_closed())
    return events


def baseline_revision() -> tuple:
    """The revision this change must not alter: the INDEX, not `HEAD`.

    MEASURED, and this matters more than it looks. On this box the worker has
    THREE states, not two:

        HEAD      6 632 lines
        index     6 714 lines   <- 82 lines of earlier work, still uncommitted
        working   6 802 lines   <- the 88 this change adds

    Differentiating against `HEAD` would blame this change for those 82 lines
    and, worse, could mask a real difference of its own. The index is the file
    as it stood immediately before this edit, which is the only honest
    comparison. `HEAD` is the fallback for a repo with nothing staged.
    """
    for spec, name in ((":worker/sotto_worker.py", "INDEX"),
                       ("HEAD:worker/sotto_worker.py", "HEAD")):
        out = subprocess.run(["git", "-C", REPO, "show", spec],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout, name
    return "", ""


#: Every `source` value the caption path can produce, each WITHOUT and WITH the
#: per-voice suffix, paired with what the shell must conclude about it.
#:
#: These are not invented. `worker/speaker_id.speaker_source` builds the suffixed
#: form as `base + "/voice:" + label`, and the bases are the ones the worker's
#: own comments name (`proc:<pid>` / `device:<name>` / `file:<name>`, plus
#: `external:` for the player's own captions).
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")
SHELL_SHAPES = [
    ("device:CABLE Output (VB-Audio Virtual Cable)", False),
    ("proc:1234", False),
    ("file:sample.wav", False),
    ("external:youtube", True),
]

SHELL_PREFIX_ARMS = [
    # `sotto_webview.py:7870` is, by an exhaustive sweep of `app/webview`,
    # `app/panel` and `worker`, the ONLY place in the product that branches on
    # a prefix of the caption's `source`. It decides whether the PLAYER's own
    # captions win over the ASR line. A per-voice suffix must not change that
    # verdict, or a Discord call would start suppressing itself the moment a
    # YouTube caption is on screen.
    ("the shell's source-prefix test is unique",
     r"source\.startswith\('external:'\)"),
    ("the voice suffix is '/voice:'",
     r'"/voice:%s"'),
]


def shell_contract_arms() -> list:
    """Does appending `/voice:speaker-N` change what the product concludes?

    Measured against the LIVE shell file, not against a copy of the expression
    written out here: the predicate is lifted out of `sotto_webview.py` and run
    over real source shapes. If someone changes that line, this arm changes
    behaviour -- which is the point.
    """
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    if not os.path.isfile(SHELL):
        chk(False, "the shell is there", SHELL)
        return out
    src = open(SHELL, encoding="utf-8").read()

    match = re.search(r"source\.startswith\('([^']+)'\)", src)
    chk(match is not None,
        "the shell branches on the caption source", repr(
            match.group(1) if match else None))
    if match is None:
        return out
    prefix = match.group(1)

    chk(prefix == "external:",
        "...and what it branches on is the PLAYER's own channel", repr(prefix))
    chk(src.count("source.startswith(") == 1,
        "...and it is the ONLY such test in the file",
        "%d occurrences" % src.count("source.startswith("))

    for base, want_external in SHELL_SHAPES:
        for label, value in (("bare", base),
                             ("suffixed", base + "/voice:speaker-2")):
            got = value.startswith(prefix)
            chk(got == want_external,
                "%s %-8s stays classified the same way (%s)"
                % (prefix, label, "external" if want_external else "not external"),
                repr(value))
    return out


def battery(lineformer_cls, baseline=None, source_text=None) -> list:
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    def fresh_provider(payload):
        return lambda: payload

    def boom():
        raise RuntimeError("the sidecar is not answering")

    # --- OFF: equal to the code before this change, event for event -------
    events = run_scenario(lineformer_cls)
    chk(bool(events), "the scenario produced events", "%d events" % len(events))
    if baseline is not None:
        chk(events == baseline,
            "OFF: events are EQUAL to the pre-change revision",
            "%d events, first differing index %s"
            % (len(events),
               next((i for i, (a, b) in enumerate(zip(events, baseline))
                     if a != b), None)))

    # --- a provider that has nothing to say changes nothing ----------------
    # UMA EXCEPCA QUE ESCAPA DO CODIGO EM TESTE E' UM VERMELHO, NAO UMA FALHA
    # DO HARNESS. Antes disto o RuntimeError do fixture `boom` subia por
    # battery() inteiro e o harness imprimia "mutante nao correu / DECORATIVO"
    # -- ou seja, um mutante COM DENTES era classificado como um que nao prova
    # nada. Sao opostos: uma coisa e' o codigo a falhar (prova), a outra e' o
    # gate a nao carregar (mentira). Agora rebenta para um check vermelho.
    for label, provider in (("no payload", fresh_provider(None)),
                            ("a provider that raises", boom)):
        try:
            got = run_scenario(lineformer_cls, provider=provider)
        except Exception as exc:                                # noqa: BLE001
            chk(False, "OFF-equivalent: " + label + " -> identical events",
                "O CODIGO EM TESTE LEVANTOU %s (%s): o event loop morreu com "
                "um provider que se porta mal" % (type(exc).__name__, exc))
            continue
        chk(got == events, "OFF-equivalent: " + label + " -> identical events",
            "%s" % ("" if got == events else "DIFFERENT"))

    # --- no source at all: the file arm and --selftest -------------------
    sourceless = run_scenario(lineformer_cls, source=None,
                              provider=fresh_provider({"segments": [
                                  {"start": 0.0, "end": 9.0, "speaker": 0}]}))
    chk(all("speaker" not in e for e in sourceless),
        "no device -> not one key added")
    chk(all("source" not in e for e in sourceless),
        "no device -> still no source key")

    # --- ON, with the REAL diarizer payload from 2026-10-18 --------------
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    fresh = run_scenario(lineformer_cls, provider=fresh_provider(payload))
    named = [e for e in fresh if e.get("speaker")]
    chk(bool(named), "ON: a real payload names somebody",
        "%d of %d" % (len(named), len(fresh)))
    chk(all(e.get("source", "").startswith(SOURCE + "/voice:") for e in named),
        "ON: and the voice gets its OWN source key",
        repr(named[0].get("source")) if named else "")
    chk(len({e.get("source") for e in named}) >= 1,
        "ON: sources are distinct per voice")
    chk(all("text" in e and e.get("text") for e in fresh),
        "ON: the WORDS are untouched -- only identity changed")
    chk(len(fresh) == len(events),
        "ON: the same events come out, not more and not fewer",
        "%d vs %d" % (len(fresh), len(events)))
    chk([e.get("text") for e in fresh] == [e.get("text") for e in events],
        "ON: text for text identical to OFF")

    # A line nobody owns keeps the device: silence is not a speaker.
    unowned = run_scenario(
        lineformer_cls,
        provider=fresh_provider({"segments": [
            {"start": 900.0, "end": 910.0, "speaker": 0}]}))
    chk(all(e.get("speaker") is None for e in unowned),
        "a line nobody holds is named by nobody")
    chk(all(e.get("source") == SOURCE for e in unowned),
        "...and keeps the DEVICE, because dropping it would be a worse lie")

    # --- the flag is off unless asked for ---------------------------------
    # THE SOURCE UNDER TEST, not the file on disk. Reading `WORKER` here made
    # every flag arm pass no matter what the mutant did -- the mutant that
    # flips `--speakers` to `store_false` was reported as SURVIVED because
    # these arms were reading the healthy file. A gate that tests something
    # other than what it is gating is worse than no gate, so the text comes in
    # as an argument and the live run passes its own.
    src = source_text if source_text is not None else open(
        WORKER, encoding="utf-8").read()
    tree = ast.parse(src)
    flag = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument":
            if node.args and isinstance(node.args[0], ast.Constant) \
                    and node.args[0].value == "--speakers":
                flag = node
    chk(flag is not None, "the flag --speakers exists")
    if flag is not None:
        kw = {k.arg: k.value for k in flag.keywords}
        # `action="store_true"` is a CONSTANT, not a Name -- a first draft of
        # this arm looked for `.id` and reported a flag that was there.
        action = kw.get("action")
        chk(action is not None and getattr(action, "value", None) == "store_true",
            "it is a plain switch", repr(action))
        chk("default" not in kw or getattr(kw.get("default"), "value", None)
            in (False, None),
            "and it defaults to OFF -- nobody gets this by accident")
        body_attrs = [ast.unparse(n) for n in tree.body
                      if isinstance(n, (ast.Import, ast.ImportFrom))]
        chk(not any("speaker_bridge" in b for b in body_attrs),
            "speaker_bridge is NOT imported at module level")

    # Structural arms -- see STRUCTURAL_GUARDS for why these two cannot be
    # behavioural. Checked against the LIVE file, once, and never counted as
    # behavioural evidence.
    for name, needle in STRUCTURAL_GUARDS:
        chk(needle in src, "structural: " + name)

    # --- a line that CROSSES a speaker boundary keeps ONE owner ----------
    # MEASURED, not designed. A line is emitted repeatedly with a GROWING
    # window, so a sentence that began inside one voice's segment can end
    # inside another's. Re-deciding every emission gave one sentence two
    # `source`s, and the panel keys its row AND its engine by that string --
    # which renders as two rows with the words duplicated. The fixture below is
    # the real four-speaker diarizer output, so the boundary is a real one.
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        fx = json.load(fh)
    raw = fx.get("segments") or []
    cross = None
    for i in range(len(raw) - 1):
        a, b = raw[i], raw[i + 1]
        if a["speaker"] != b["speaker"] and a["end"] - a["start"] > 1.0 \
                and b["end"] - a["end"] > 1.0:
            cross = (a, b)
            break
    chk(cross is not None, "the fixture has a real speaker boundary to cross")
    if cross is not None:
        a, b = cross
        t0 = round(a["start"] + 0.2, 2)
        small = round(a["end"] - 0.1, 2)
        big = round(b["end"] - 0.3, 2)
        former = lineformer_cls(min_chars=1, emit_partial=True, source=SOURCE)
        former.set_speaker_provider(lambda: fx)
        e1 = former.push("e eu", t0, small, False)
        e2 = former.push("e eu quero que o alt c", t0, big, False)
        named = [e for e in (e1 + e2) if e.get("speaker")]
        chk(bool(named), "the crossing line produced attributed events",
            "%d of %d" % (len(named), len(e1) + len(e2)))
        srcs = sorted({e.get("source") for e in named})
        chk(len(srcs) == 1,
            "a line that CROSSES a speaker boundary keeps ONE source", repr(srcs))

        former.reset()
        # 1,0 s of overlap, not 0,3 s: the floor is `>= 0.30` and a window that
        # lands EXACTLY on the floor is a coin toss in floating point. A gate
        # that fails on its own arithmetic is a gate nobody trusts.
        t1 = round(b["end"] - 1.0, 2)
        former.push("e ai pessoal", t1, round(b["end"], 2), False)
        nxt = former.push("e ai pessoal tudo bem", t1,
                          round(b["end"] + 0.4, 2), False)
        nxt_src = sorted({e.get("source") for e in nxt if e.get("speaker")})
        chk(len(nxt_src) == 1, "the next line decides on its own", repr(nxt_src))
        chk(nxt_src != srcs,
            "and two consecutive lines from two people get two sources",
            "%r vs %r" % (nxt_src, srcs))

    # --- THE CASE THAT ACTUALLY CHANGES HANDS, built on purpose ----------
    # The fixture's first segment is 6,5 s long, so a line grown from it never
    # gives the floor to the next speaker: re-deciding every emission and
    # locking on the first one produced the SAME answer, and the fixture
    # therefore could not tell them apart. That is why this arm exists --
    # a gate that cannot fail is not a gate. Here speaker-1 holds 0,4 s of
    # the first emission and speaker-2 holds 4,8 s of the second, so the two
    # implementations MUST disagree.
    flip = {"segments": [{"start": 0.0, "end": 0.6, "speaker": 0},
                         {"start": 0.7, "end": 6.0, "speaker": 1}]}
    f2 = lineformer_cls(min_chars=1, emit_partial=True, source=SOURCE)
    f2.set_speaker_provider(lambda: flip)
    p1 = f2.push("e eu", 0.1, 0.5, False)
    p2 = f2.push("e eu quero que o alt c", 0.1, 5.5, False)
    flip_src = sorted({e.get("source") for e in p1 + p2 if e.get("speaker")})
    chk(len(flip_src) == 1,
        "a line that CHANGES HANDS keeps ONE source", repr(flip_src))
    chk(bool(p1) and p1[0].get("speaker") is not None,
        "and the FIRST emission already names its owner",
        repr([e.get("speaker") for e in p1]))
    chk(bool(p2) and p2[-1].get("speaker") is not None,
        "and the last one agrees",
        repr([e.get("speaker") for e in p2]))

    # The shell's own contract, read from the LIVE file.
    out.extend(shell_contract_arms())

    return out


MUTANTS = [
    # The one that matters most: a flag that is ON but has no payload must still
    # produce exactly the old events. This was a REAL defect -- the first cut
    # stamped `speaker: None` onto every caption -- and the arm that caught it
    # is "no payload -> identical events".
    ("stamp-speaker-even-with-no-payload",
     "            if payload is None:\n                return event",
     "            if payload is False:\n                return event"),
    ("the-speaker-field-is-forgotten",
     '            event["speaker"] = speaker\n',
     '            pass\n'),
    ("the-voice-loses-its-own-source",
     '            event["source"] = got.get("source") or event["source"]',
     '            event["source"] = event["source"]'),
    ("a-crash-in-the-sidecar-kills-the-caption",
     "        except Exception:                                             # noqa: BLE001\n            return event",
     "        except ZeroDivisionError:                                    # noqa: BLE001\n            return event"),
    ("the-flag-defaults-to-ON",
     '        "--speakers",\n        action="store_true",',
     '        "--speakers",\n        action="store_false",'),
    # The line-owner lock. Without it a sentence that straddles two voices
    # gets two `source`s and the panel paints it twice.
    ("the-line-owner-is-re-decided-every-emission",
     "        if self._speaker_decided:",
     "        if False:"),
]

#: Arms that CANNOT be behavioural, and why. Two guards are load-bearing for
#: robustness but produce identical OUTPUT when removed, because the fail-safe
#: swallows the very error they would have avoided:
#:
#:   `if provider is None ...`   removing it calls `None()` -> TypeError ->
#:                               swallowed -> the same event comes out
#:   `or event.get("source")...`  removing it does `event["source"]` on a
#:                               sourceless event -> KeyError -> swallowed ->
#:                               the same event comes out
#:
#: Both are therefore checked in the SOURCE, and are labelled structural so
#: nobody later counts them as behavioural evidence. A gate that pretends to
#: catch what it cannot is worse than one that admits it.
STRUCTURAL_GUARDS = [
    ("guard: no provider, no attribution",
     'if provider is None or event.get("source") is None:'),
    ("guard: attribution never runs on a sourceless event",
     'event.get("source") is None:'),
]


def main() -> int:
    if not os.path.isfile(WORKER):
        print("RED   worker missing: %s" % WORKER)
        return EXIT_FAIL
    head, rev_name = baseline_revision()
    if not head:
        print("RED   cannot read the pre-change worker -- the differential test "
              "needs it and will not be faked")
        return EXIT_FAIL
    live_src = open(WORKER, encoding="utf-8").read()
    # `LineFormer._attribute` does `import speaker_bridge`, exactly as the worker
    # does at runtime -- the script's own directory is what makes that work.
    # Without this line the import raises, the fail-safe swallows it, and the
    # whole ON arm silently measures nothing while reporting GREEN. That is not
    # a hypothetical: it is what the first run of this oracle did, and the two
    # mutantes that touch the exception handler "passed" for the wrong reason.
    sys.path.insert(0, os.path.join(REPO, "worker"))

    print("DIFFERENTIAL (the revision this change must not alter)")
    print("  baseline = %s  lines=%d"
          % (rev_name, len(head.splitlines())))
    print("  working  = tree  lines=%d" % len(live_src.splitlines()))

    print("\nARMS (the real worker)")
    baseline = run_scenario(extract_lineformer(head))
    live = extract_lineformer(live_src)
    rows = battery(live, baseline, source_text=live_src)
    for ok, name, detail in rows:
        print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                             ("  " + detail) if detail else ""))
    green = sum(1 for ok, _, _ in rows if ok)
    print("\n  %d/%d" % (green, len(rows)))

    print("\nNEGATIVE ARM (broken plumbing must go RED)")
    caught = 0
    weak = 0
    tmp = tempfile.mkdtemp(prefix="speaker-plumbing-")
    try:
        for idx, (label, old, new) in enumerate(MUTANTS):
            if old not in live_src:
                print("  RED   mutant %-46s ANCHOR MISSING -- oracle is stale"
                      % label)
                weak += 1
                continue
            broken = live_src.replace(old, new, 1)
            # CARREGAR e CORRER sao coisas diferentes e nunca podem ser
            # confundidas: se a copia nao carrega, o mutante nao foi testado
            # (decorativo); se carrega mas rebenta a bateria, o codigo partiu
            # mas o gate nao consegue dizer QUAL check o apanhou -- tambem nao
            # cumpre o que promete. Nenhum dos dois pode virar "caught".
            try:
                broken_cls = extract_lineformer(broken)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-46s DECORATIVO: nao carregou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            try:
                res = battery(broken_cls, baseline, source_text=broken)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-46s INCONCLUSIVO: carregou mas a "
                      "bateria morreu antes de um check nomeado (%s)"
                      % (label, type(exc).__name__))
                weak += 1
                continue
            reds = [name for ok, name, _ in res if not ok]
            if reds:
                print("  GREEN mutant %-46s caught by: %s"
                      % (label, "; ".join(reds[:2])))
                caught += 1
            else:
                print("  RED   mutant %-46s SURVIVED -- the gate is blind here"
                      % label)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(MUTANTS)
    ok = green == len(rows) and caught == total and weak == 0
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", green, len(rows), caught, total))
    if weak:
        print("  %d mutante(s) DECORATIVO(S): nao correram, logo nao provaram "
              "nada. Um braco negativo que promete %d e testa %d nao cumpre."
              % (weak, total, caught))
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())