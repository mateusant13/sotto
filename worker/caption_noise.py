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

# UM BLOCO DE LETRAS DE OUTRO ALFABETO NAO E' TRANSCRICAO DESTE MOTOR
# (medido 2026-11-10). O corpus de `history/2026-11-0*/*.md` tem **25 linhas**
# com escrita nao-latina, TODAS `producer=redux` (o motor de lote), e elas nao
# sao fala mal reconhecida por acaso -- sao o modelo a escorregar para outra
# lingua a meio da janela:
#   `- [12:52:42] Тава кусада, движе.`            (12.md)
#   `- [01:44:51] Unreal text. Gotta make you Я говорю на кем I gotta let you now.`
#   `- [13:38:19] Σκάστο μονίνεται ορημαθείο, ...` (13.md, grego)
# O motor de fundo e' `parakeet`/ingles: a escrita DELE e' latina, sempre, e um
# bloco de >=2 letras fora dela so' pode ser alucinacao (o mesmo mecanismo que o
# `caption_noise` ja' cura para o `Mmm`). O limiar e' 2 e nao 3 porque uma
# sequencia de duas letras ja' e' uma palavra estrangeira a comecar; uma letra
# isolada (uma sigla citada, "Я") fica, para o predicado nao punir o caso unico
# que o corpus dele nunca mostrou como defeito.
_SCRIPT_MIN_RUN = 2
_SCRIPT_CLASS = ("\u0400-\u04FF" "\u0370-\u03FF" "\u0590-\u05FF"
                 "\u0600-\u06FF" "\u0E00-\u0E7F" "\u3040-\u30FF"
                 "\u4E00-\u9FFF" "\uAC00-\uD7AF")
_SCRIPT_RUN = re.compile("[%s]{%d,}" % (_SCRIPT_CLASS, _SCRIPT_MIN_RUN))


def is_foreign_script_caption(text, min_run=_SCRIPT_MIN_RUN):
    """True when the caption carries a run of letters from another alphabet.

    The unit is the caption, like `is_noise_caption`: a line that got its first
    words right and then slid into Russian is not half a transcription, it is a
    wrong one, and the next window re-decodes the tail. The engine is English
    (Latin script), so EVERY other block is a foreign one -- the ranges below
    cover Cyrillic, Greek, Hebrew, Arabic, Thai, kana, han and hangul.
    """
    pattern = (_SCRIPT_RUN if min_run == _SCRIPT_MIN_RUN
               else re.compile("[%s]{%d,}" % (_SCRIPT_CLASS, min_run)))
    return bool(pattern.search(str(text or "")))


def is_noise_caption(text):
    """True only when the WHOLE caption is non-lexical filler ("Mmm Mmm.").

    The unit is the caption, not the token: a filler next to a real word is
    part of speech and is kept. `fullmatch` makes the whole-word requirement
    atomic, so `Mmmm` matches but `Mmm hmm, mas` does not.
    """
    words = str(text or "").split()
    return bool(words) and all(_NOISE_WORD.fullmatch(word) for word in words)


def admit_batch_caption(sw, text):
    """False when `text` is noise or foreign script; count it on the switch.

    One choke point, two rules, two counters: `noise_lines` for the `Mmm` class
    and `script_lines` for the other alphabet, so the batch log says WHICH rule
    removed a window -- a single counter would make the two indistinguishable in
    the very log the owner reads.
    """
    if is_noise_caption(text):
        sw.noise_lines = getattr(sw, "noise_lines", 0) + 1
        return False
    if is_foreign_script_caption(text):
        sw.script_lines = getattr(sw, "script_lines", 0) + 1
        return False
    return True


def _corpus_arm(check):
    """O braco da CORPUS: a cobertura do padrao, medida sobre o historico DELE.

    Toda linha com escrita de outro alfabeto tem de ser recusada; se um intervalo
    do `_SCRIPT_CLASS` faltar, `refused` cai abaixo de `with_foreign` e o numero
    denuncia-o -- e' o unico jeito de a corpus provar a COBERTURA do padrao em vez
    de o repetir. A corpus vive em `history/`, que e' git-ignored e so' existe na
    arvore principal: num worktree o braco diz SKIP e nao conta como verde.
    """
    import glob
    import os

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = sorted(glob.glob(os.path.join(repo, "history", "2026-11-0*", "*.md")))
    if not files:
        print("SKIP corpus -- sem history/ nesta arvore; o braco do alfabeto "
              "correu sobre as 13 frases de cima")
        return
    refused = with_foreign = latin = 0
    missed = []
    foreign_re = re.compile("[%s]" % _SCRIPT_CLASS)
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "]" not in line:
                    continue
                body = line.split("]", 1)[1].split("<!--")[0].strip()
                if not body:
                    continue
                has_foreign = bool(foreign_re.search(body))
                with_foreign += 1 if has_foreign else 0
                latin += 0 if has_foreign else 1
                if is_foreign_script_caption(body):
                    refused += 1
                    if not has_foreign:
                        missed.append(body[:60])
    check("corpus: refused == lines with foreign script, zero latin refused",
          with_foreign > 0 and refused == with_foreign and not missed,
          {"files": len(files), "foreign": with_foreign, "refused": refused,
           "latin": latin, "unexpected": missed[:5]})


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

    # 4. O ALFABETO (medido na corpus do dono, 2026-11-10): as linhas que o
    # motor de lote devolveu em cirilico/grego sao alucinacao, e as latinas com
    # acento NAO sao. O predicado e' por linha inteira, como o do `Mmm`.
    foreign = [
        "Тава кусада, движе.",
        "Но выстраиваю.",
        "Unreal text. Gotta make you Я говорю на кем I gotta let you now.",
        "Σκάστο μονίνεται ορημαθείο, νούτο το κόκκινο.",
        "Sobre Видите, как са...",
        "Да шашка.",
    ]
    latin = [
        "Mmm, mas eu vou.",
        "João não sabia, cabeça!",
        "Tokyo and Putin are names in Latin letters.",
        "Ação, coração, ãõçéê.",
        "Я",                     # uma letra sozinha fica: nao e' bloco
        "",
        None,
    ]
    check("foreign-script captions are refused",
          all(is_foreign_script_caption(t) for t in foreign),
          [t for t in foreign if not is_foreign_script_caption(t)])
    check("latin captions are not refused",
          not any(is_foreign_script_caption(t) for t in latin),
          [t for t in latin if is_foreign_script_caption(t)])

    # 5. O CALL SITE com a regra nova: a janela em cirilico nao publica nada e
    # o contador do log e' o `script_lines`, nao o `noise_lines` -- um contador
    # so' tornaria as duas regras indistinguiveis exactamente no log que o dono
    # le.
    sw = run(["Тава кусада, движе.", "hello world"])
    captions = [x for x in sw._captions.items if x.get("type") == "caption"]
    check("a cyrillic window publishes nothing and the real one survives",
          [x.get("text") for x in captions] == ["hello world"], captions)
    check("the batch log says script_lines=1, not noise_lines",
          any("script_lines=1" in line for line in sw.logs)
          and any("noise_lines=0" in line for line in sw.logs), sw.logs)

    # 6. A CORPUS DO DONO, contada (funcao propria: o `_selftest` ja' e' o maior
    # corpo deste ficheiro e o ratchet estrutural pune o crescimento dele).
    _corpus_arm(check)

    # 7. NEGATIVE ARM: empty the pattern; the same two windows must both publish.
    # `run_engine_pass` holds the function imported from THIS module; when this
    # file is executed as `__main__`, the policy's copy is a SECOND module, so
    # mutate the one the call site actually reads.
    import sys

    noise_mod = sys.modules[policy.admit_batch_caption.__module__]
    original = noise_mod._NOISE_WORD
    original_script = noise_mod._SCRIPT_RUN
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

    # 7-bis. O MESMO CONTROLO PARA A REGRA NOVA, e separado de proposito: um
    # negativo que so' desarma o `Mmm` deixaria a regra do alfabeto sem prova
    # nenhuma -- o defeito que esta casa chama "um controlo que nao pode falhar",
    # do lado de quem acha que provou as duas metades.
    neg_script_ok = False
    neg_script_evidence = []
    try:
        noise_mod._SCRIPT_RUN = re.compile(r"(?!)")
        sw = run(["Тава кусада, движе.", "hello world"])
        captions = [x for x in sw._captions.items if x.get("type") == "caption"]
        neg_script_ok = [x.get("text") for x in captions] == [
            "Тава кусада, движе.", "hello world"]
        neg_script_evidence = [x.get("text") for x in captions]
    finally:
        noise_mod._SCRIPT_RUN = original_script
    check("negative arm of the script rule (the cyrillic window publishes again)",
          neg_script_ok, neg_script_evidence)

    ok = all(good for _name, good, _evidence in checks)
    for name, good, evidence in checks:
        print(("PASS " if good else "FAIL ") + name + " -- " + json.dumps(evidence, ensure_ascii=False)[:300])
    print(json.dumps({
        "ok": ok,
        "cases": len(checks),
        "caught": sum(1 for _n, good, _e in checks if good),
        "neg_arm": "PASS" if neg_ok else "FAIL",
        "neg_arm_script": "PASS" if neg_script_ok else "FAIL",
    }, ensure_ascii=False))
    both_neg = neg_ok and neg_script_ok
    print("NEG-ARM: PASS" if both_neg else "NEG-ARM: FAIL")
    return 0 if (ok and both_neg) else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
