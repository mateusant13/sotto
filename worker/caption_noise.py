"""A WHOLE CAPTION MADE ONLY OF NON-LEXICAL FILLER IS NOT A TRANSCRIPTION.

MEASURED on `history/2026-11-09/*.md` (680 lines, 15:00Z onward): **93 lines
(13.7 %) are exactly `Mmm`, `Mmm.` or a run of `Mmm`**, every one of them
`producer=redux`; in `14.md` they are 25 of 49 lines (51 %). The owner's
transcript is the thing he reads, and these lines carry no word in any
language -- the batch engine heard music/room tone and emitted its filler
token. Filtering them is a string check per emitted window, not a second
decode: `timeit` over the shipped predicate is ~2.4 us for the longest corpus
line and ~1.7 us for a real 90-char line, i.e. <=1.6 us of CPU per AUDIO
second at one call per 3 s window -- against the batch engine's measured
~0.745 s compute for 14.6 s of audio.

The predicate NEVER touches a line that also contains a real word
(`Mmm, mas eu vou.` stays), and it does not drop the other single-word lines
the corpus contains (`Oh.`, `Sim`, `Cabeça!`), because those can be speech.
It is deliberately narrow: the whole caption must consist of `m`/`hm`/`mhm`
tokens with terminal punctuation.

WHY THIS IS A MODULE OF ITS OWN. The structural ratchet
(`_main/code-health-oracle.py`) forbids growing a file already in its
baseline; a new file is the sanctioned place for extracted code. `engine_policy`
imports `admit_batch_caption` from here and uses it in `run_engine_pass`; the
module itself imports nothing from the worker, so it can be tested alone.

ORACLE: `python worker/caption_noise.py --selftest` (7 arms; the last one is
the negative arm that empties the pattern and requires both noise windows to
publish, so the rule -- not the harness -- is what removed them).
"""
from __future__ import annotations

import re

_NOISE_WORD = re.compile(r"(?:m+|hm+|mhm+)[.,!?…]*", re.IGNORECASE)


def is_noise_caption(text):
    """True only when the WHOLE caption is non-lexical filler ("Mmm Mmm.").

    The unit is the caption, not the token: a filler next to a real word is
    part of speech and is kept. `fullmatch` makes the whole-word requirement
    atomic, so `Mmmm` matches but `Mmm hmm, mas` does not.
    """
    words = str(text or "").split()
    return bool(words) and all(_NOISE_WORD.fullmatch(word) for word in words)


def admit_batch_caption(sw, text):
    """False when `text` is noise; count it on the switch for the batch log."""
    if not is_noise_caption(text):
        return True
    sw.noise_lines = getattr(sw, "noise_lines", 0) + 1
    return False


def _selftest():
    """Prove the rule and its CALL SITE, in two colours.

    Positive arm: a pass whose windows are all `Mmm` publishes zero captions,
    and the log says how many were dropped. Control arm: a window with a real
    word still publishes. Negative arm: empty the pattern and the SAME pass
    must publish both noise windows -- the rule is what removed them, not the
    harness or the fake engine.
    """
    import json

    import engine_policy as policy

    class _Captions:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

    class _Engine:
        dir = "models/fake"
        loads = 0

        def __init__(self, texts):
            self.texts = list(texts)

        def name(self):
            return "fake"

        def load(self):
            self.loads += 1
            return self

        def transcribe(self, _chunk):
            return self.texts.pop(0) if self.texts else ""

    class _Switch:
        rate = 16000
        engine_window_s = policy.REDUX_ENGINE_WINDOW_S
        mode = "normal"
        producer = "redux"
        segments = 0
        segment_lines = 0

        def __init__(self, texts):
            self.engine = _Engine(texts)
            self._captions = _Captions()
            self.logs = []
            self.parked = []

        def log(self, message):
            self.logs.append(message)

        def rss(self):
            return 0.0

        def _park(self, held, reason, extra=""):
            self.parked.append((reason, extra))

        def _release_engine(self, reason):
            self.logs.append("RELEASE " + reason)

    import numpy as np

    def run(texts):
        sw = _Switch(texts)
        held = [np.zeros(int(sw.rate * sw.engine_window_s * len(texts)), dtype="float32")]
        policy.run_engine_pass(sw, held, held[0].size, "selftest")
        return sw

    checks = []

    def check(name, good, evidence):
        checks.append((name, bool(good), evidence))

    # 1. the predicate, both colours
    positive = ["Mmm", "Mmm.", "Mmm Mmm Mmm Mmm Mmm.", "Hmm.", "Mhm,"]
    controls = ["Mmm, mas eu vou.", "Mmm hmm, mas eu vou.", "Uh.", "Oh.", "Sim", "Melena."]
    check("noise-only captions are noise",
          all(is_noise_caption(t) for t in positive),
          [t for t in positive if not is_noise_caption(t)])
    check("captions with a real word are not noise",
          not any(is_noise_caption(t) for t in controls),
          [t for t in controls if is_noise_caption(t)])

    # 2. the real call site: two noise windows publish nothing
    sw = run(["Mmm.", "Mmm Mmm."])
    captions = [x for x in sw._captions.items if x.get("type") == "caption"]
    statuses = [x for x in sw._captions.items if x.get("type") == "status"]
    check("noise windows publish zero captions", len(captions) == 0, captions)
    check("all-noise pass logs noise_lines=2",
          any("noise_lines=2" in line for line in sw.logs), sw.logs)
    check("all-noise pass reports redux-batch-empty",
          any(x.get("state") == "redux-batch-empty" for x in statuses), statuses)

    # 3. control: a real word in the second window still publishes
    sw = run(["Mmm.", "hello world"])
    captions = [x for x in sw._captions.items if x.get("type") == "caption"]
    check("a real word survives beside a noise window",
          [x.get("text") for x in captions] == ["hello world"], captions)

    # 4. NEGATIVE ARM: empty the pattern; the same two windows must both publish.
    # `run_engine_pass` holds the function imported from THIS module; when this
    # file is executed as `__main__`, the policy's copy is a SECOND module, so
    # mutate the one the call site actually reads.
    import sys

    noise_mod = sys.modules[policy.admit_batch_caption.__module__]
    original = noise_mod._NOISE_WORD
    neg_ok = False
    neg_evidence = []
    try:
        noise_mod._NOISE_WORD = re.compile(r"(?!)")
        sw = run(["Mmm.", "Mmm Mmm."])
        captions = [x for x in sw._captions.items if x.get("type") == "caption"]
        neg_ok = len(captions) == 2
        neg_evidence = [x.get("text") for x in captions]
    finally:
        noise_mod._NOISE_WORD = original
    check("negative arm re-breaks it (both noise windows publish)", neg_ok,
          neg_evidence)

    ok = all(good for _name, good, _evidence in checks)
    for name, good, evidence in checks:
        print(("PASS " if good else "FAIL ") + name + " -- " + json.dumps(evidence, ensure_ascii=False)[:300])
    print(json.dumps({
        "ok": ok,
        "cases": len(checks),
        "caught": sum(1 for _n, good, _e in checks if good),
        "neg_arm": "PASS" if neg_ok else "FAIL",
    }, ensure_ascii=False))
    print("NEG-ARM: PASS" if neg_ok else "NEG-ARM: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
