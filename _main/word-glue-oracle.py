"""ORACLE for the WORD-GLUE class in `worker/sotto_worker.py` (lane WordSplitFast).
# NO-BUG: mede a CLASSE do seam de palavras ("very fa st") no worker que embarca; a classe nao tem id no leder

THE DEFECT (owner, 2026-11-05, verbo ad verbum)
------------------------------------------------
*"acabei de ver alguem falando very fast e a legenda saindo very fa st. entenda
por que a nossa normalizacao de frases ou palavras ta ruim e arruma."*

MEDIDO no log vivo do dono (`_main/webview-run.log`, 16:11):

    16:11:11.646 CAPTION_IN ... final=false text="fa st listen"
    16:11:12.200 CAPTION_IN ... text="fa st listen to this"
    16:11:13.315 CAPTION_IN ... text="fa st listen to this it even matches GPT"
    16:11:13.910 CAPTION_IN ... text="fa st listen to this it even matches GPT six"

Um chunk decodificou `fa`, o seguinte decodificou `▁st listen ...`: o token do
seam leva a marca de inicio de palavra, `chunk_is_continuation` devolve False, e
`join_fragments` insere um espaco. A classe e' mais larga que este caso -- o
censo de main sobre as mesmas 11 465 linhas deu 293 linhas com um `s` solto
entre duas palavras (`it s outside` 10, `make s sense` 9, `cheater s are` 9,
`inteiro s que` 8, `mini s que` 8, `stain s yet` 10).

A CURA, e ela e' UMA so' (`join_fragments`, o unico lugar que decide separador):
  * `glues_split_word`/`glue_split_seams`: uma cauda de 1-2 letras minusculas com
    vogal mais uma cabeca sem vogal (`fa`|`st`) sao UMA palavra partida;
  * `glue_lone_s`: um token que e' exatamente `s` entre duas letras cola ao
    anterior (`it s outside` -> `its outside`).

Nenhuma das duas le um dicionario, um LM ou a rede: so' os caracteres do seam.

ESTE ORACULO
------------
Importa o modulo REAL `worker/sotto_worker.py` (nunca uma copia da logica) e
exercita `join_fragments` e o `LineFormer` de verdade.

  normal run   0 = PASS ("VERDICT: PASS"), 1 = FAIL, 2 = setup error
  --neg-arm    muta as DUAS linhas da cura numa COPIA do worker (cada ancora
               contada, tem de ocorrer exatamente uma vez), exige que TODA arma
               de CURA fique VERMELHA e toda invariante fique VERDE, e termina
               com `NEG-ARM: PASS` e rc=1 (a bateria pede rc=1 ao braco
               negativo). Mutante que sobrevive = rc=0, ancoras decorativas =
               rc=2.

Sem janela, sem audio, sem modelo: so' import de texto.
"""

from __future__ import annotations

import atexit
import importlib.util
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER_DIR = os.path.join(REPO, "worker")
WORKER_FILE = os.path.join(WORKER_DIR, "sotto_worker.py")

# The import has to find `stable_words` / `engine_switch` beside the worker.
if WORKER_DIR not in sys.path:
    sys.path.insert(0, WORKER_DIR)

#: O caso medido, fragmento por fragmento, na ordem em que o modelo os cuspiu.
MEASURED_FRAGS = [
    ("fa", False),
    ("st listen to this", False),
    ("it even matches GPT", False),
    ("six", False),
]
MEASURED_WANT = "fast listen to this it even matches GPT six"


def load_worker(path, name):
    """The REAL worker module, loaded from `path` under `name`."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── AS ARMADAS ────────────────────────────────────────────────────────────────
# (nome, e_arma_de_cura, funcao(W) -> texto, esperado)
ARMS = [
    # o defeito medido, no join puro
    ("measured 'fa'|'st listen ...' glues to 'fast listen ...'",
     True,
     lambda W: W.join_fragments(MEASURED_FRAGS),
     MEASURED_WANT),
    # o MESMO caso pelo `LineFormer`, que e' o que vai a' tela (parcial e fecho)
    ("measured case through the real LineFormer (partial + closed line)",
     True,
     lambda W: "|".join(
         [e["text"] for e in _former_run(W, MEASURED_FRAGS)]
     ),
     "fast listen to|fast listen to this it even matches|"
     "fast listen to this it even matches GPT|"
     "fast listen to this it even matches GPT six|"
     "fast listen to this it even matches GPT six"),
    # a classe do `s` solto, com as cadeias EXACTAS do censo
    ("lone-s 'it s outside' -> 'its outside'",
     True,
     lambda W: W.join_fragments([("it", False), ("s outside", False)]),
     "its outside"),
    ("lone-s 'make s sense' (inside one chunk) -> 'makes sense'",
     True,
     lambda W: W.join_fragments([("make s sense", False)]),
     "makes sense"),
    ("lone-s 'cheater s are' -> 'cheaters are'",
     True,
     lambda W: W.join_fragments([("cheater", False), ("s are", False)]),
     "cheaters are"),
    ("lone-s 'inteiro s que' -> 'inteiros que'",
     True,
     lambda W: W.join_fragments([("inteiro", False), ("s que", False)]),
     "inteiros que"),
    ("lone-s 'mini s que' -> 'minis que'",
     True,
     lambda W: W.join_fragments([("mini", False), ("s que", False)]),
     "minis que"),
    ("lone-s 'stain s yet' -> 'stains yet'",
     True,
     lambda W: W.join_fragments([("stain", False), ("s yet", False)]),
     "stains yet"),
    # ── FRONTEIRAS GENUINAS: nunca colam ─────────────────────────────────────
    ("boundary 'and the' stays separated",
     False,
     lambda W: W.join_fragments([("and", False), ("the", False)]),
     "and the"),
    ("boundary 'I am' stays separated (uppercase head)",
     False,
     lambda W: W.join_fragments([("I", False), ("am", False)]),
     "I am"),
    ("boundary 'do you' stays separated (voweled head)",
     False,
     lambda W: W.join_fragments([("do", False), ("you", False)]),
     "do you"),
    ("boundary 'saudade eterna' stays separated (long tail)",
     False,
     lambda W: W.join_fragments([("saudade", False), ("eterna", False)]),
     "saudade eterna"),
    ("boundary 'it even' stays separated (voweled head after short tail)",
     False,
     lambda W: W.join_fragments([("it", False), ("even", False)]),
     "it even"),
    # ── A CURA NAO ATRAVESSA PONTUACAO NEM LINHA TERMINAL ────────────────────
    ("terminal barrier: 'entendi.'|'st listen' never glues",
     False,
     lambda W: W.join_fragments([("entendi.", False), ("st listen", False)]),
     "entendi. st listen"),
    ("terminal barrier: 'fast.'|'st' never glues",
     False,
     lambda W: W.join_fragments([("fast.", False), ("st", False)]),
     "fast. st"),
    # ── O `s` SOLTO NAO E' TOCADO FORA DO MEIO DE DUAS PALAVRAS ─────────────
    ("lone-s at line start stays ('s a')",
     False,
     lambda W: W.join_fragments([("s", False), ("a", False)]),
     "s a"),
    ("lone-s after punctuation stays ('espero.'|'s que')",
     False,
     lambda W: W.join_fragments([("espero.", False), ("s que", False)]),
     "espero. s que"),
    # ── O COMPORTAMENTO DO SEAM_REPEAT NAO MUDOU ────────────────────────────
    ("'nao nao' survives (one repeated word is speech)",
     False,
     lambda W: W.join_fragments([("nao", False), ("nao", False)]),
     "nao nao"),
    ("repeated tail collapses ('tem umas' x2)",
     False,
     lambda W: W.join_fragments(
         [("tem", False), ("umas", False), ("tem umas", False),
          ("youtuber que", False)]),
     "tem umas youtuber que"),
    ("SEAM_REPEAT_MIN_WORDS is still 2",
     False,
     lambda W: W.SEAM_REPEAT_MIN_WORDS,
     2),
    # ── O PARCIAL E O FECHO CONTAM A MESMA HISTORIA ────────────────────────
    # `stable_words.open_word_start` reconstroi a linha por conta propria, por
    # isso o contrato e' claro: quem lhe entrega fragmentos entrega-os JA'
    # fundidos. Esta arma prova a metade que precisa de ser verdadeira.
    ("proven prefix is a prefix of the joined line (glued frags)",
     True,
     lambda W: _prefix_agrees(W, MEASURED_FRAGS),
     True),
    ("control: RAW frags diverge -- the merge is what the partial needs",
     True,
     lambda W: _prefix_agrees(W, None),
     False),
]


def _prefix_agrees(W, frags):
    """O provado e' prefixo do texto unido? `None` = de proposito, com os crus."""
    glued = W.glue_split_seams(MEASURED_FRAGS)
    if frags is None:
        glued = MEASURED_FRAGS
    proven, _tail = W._stable_words().proven_text(glued)
    return W.join_fragments(MEASURED_FRAGS).startswith(proven) and bool(proven)


def _former_run(W, frags):
    """Os eventos de um `LineFormer` REAL sobre `frags`: parciais e fecho.

    O parcial vem de `stable_words.proven_text` (a ultima palavra por provar), o
    fecho de `LineFormer._close`. Os dois tem de contar a MESMA historia: se o
    parcial dissesse "fa st" e o fecho "fast", a cura estaria so' na metade.
    """
    former = W.LineFormer(min_chars=1, emit_partial=True)
    events = []
    for i, (text, _cont) in enumerate(frags):
        events += former.push(text, start=i * 0.56, end=(i + 1) * 0.56)
    events += former.flush()
    events += former.take_closed()
    return events


def arm(name, got, want, fix_arm):
    ok = got == want
    tag = "" if fix_arm else "   (invariant/control)"
    print(f"[{'PASS' if ok else 'FAIL'}] arm: {name}{tag}")
    print(f"       got  = {got!r}")
    print(f"       want = {want!r}")
    return ok


MUTATIONS = [
    # the seam rule: no merging at the join
    ("    for text, cont in glue_split_seams(frags):",
     "    for text, cont in frags:"),
    # the lone-`s` rule: no gluing after the join
    ("    return dedup_seam_repeat(glue_lone_s(out.strip()))",
     "    return dedup_seam_repeat(out.strip())"),
]


def mutant_worker():
    """A COPY of the shipped worker with the TWO cure lines reverted.

    The anchors are TEXTUAL and each is COUNTED. An anchor that is missing (the
    oracle went stale) or appears more than once is decorative: it proves
    nothing, so this refuses to count it and exits 2.
    """
    with open(WORKER_FILE, encoding="utf-8", newline="") as fh:
        text = fh.read()
    for old, new in MUTATIONS:
        hits = text.count(old)
        if hits != 1:
            print(f"SETUP: anchor occurs {hits}x (need exactly 1): {old!r}")
            return None
        text = text.replace(old, new, 1)
    tmpdir = tempfile.mkdtemp(prefix="word-glue-mutant-")
    atexit.register(shutil.rmtree, tmpdir, True)
    copy = os.path.join(tmpdir, "sotto_worker.py")
    with open(copy, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return load_worker(copy, "sotto_worker_word_glue_mutant")


def main():
    neg = "--neg-arm" in sys.argv

    if neg:
        W = mutant_worker()
        if W is None:
            return 2
        print("== NEG-ARM: the cure is OFF in a COPY of the worker ==")
        survived, blinded = [], []
        for name, fix_arm, run, want in ARMS:
            got = run(W)
            ok = got == want
            if fix_arm:
                verdict = "SURVIVED" if ok else "RED"
                if ok:
                    survived.append(name)
            else:
                verdict = "PASS" if ok else "POISONED"
                if not ok:
                    blinded.append(name)
            print(f"[{verdict}] {'fix' if fix_arm else 'inv'} arm: {name}")
            print(f"       mutant = {got!r}")
            print(f"       want   = {want!r}")
        if survived:
            print("NEG-ARM: FAIL -- the mutant was NOT caught by:")
            for n in survived:
                print(f"   blind to: {n}")
            return 0
        if blinded:
            print("NEG-ARM: FAIL -- the mutant poisoned invariant arms (the arm "
                  "set is wrong, not the cure):")
            for n in blinded:
                print(f"   poisoned: {n}")
            return 0
        print(f"NEG-ARM: PASS -- {len(ARMS)} arms, every fix arm RED, every "
              f"invariant GREEN")
        return 1

    W = load_worker(WORKER_FILE, "sotto_worker_word_glue")
    failed = 0
    for name, fix_arm, run, want in ARMS:
        if not arm(name, run(W), want, fix_arm):
            failed += 1
    print(f"\n{len(ARMS) - failed}/{len(ARMS)} arms green")
    print("VERDICT: PASS" if not failed else "VERDICT: FAIL")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
