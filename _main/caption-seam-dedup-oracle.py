#!/usr/bin/env python3
"""A REPETICAO NO SEAM DO CHUNK -- medida, e a cura provada num so' lugar.

O DEFEITO (2026-11-02, na captura real do dono). Rodando o caminho VIVO sobre
30 s do loopback `VoiceMeeter Input` (`SOTTO_FILE_TAP`), os textos dos chunks
foram, verbatim:

    14,00-14,56 'caramba'   16,24-16,80 'tem'   16,80-17,36 'umas'
    17,36-17,92 'tem umas'  17,92-18,48 'youtuber que' ...

e a linha publicada era

    'caramba tem umas tem umas youtuber que elas só são sapadas mesmo não é'

O chunk seguinte re-decodifica o rabo do anterior e o emite OUTRA VEZ. O carry
do predictor entre chunks nao pode ser desligado para "curar" isto: medido no
MESMO audio, com o carry desarmado o run inteiro morre para `Caram Tem`. Logo a
cura e' de TEXTO (`dedup_seam_repeat`), na unica funcao que decide o texto
(`join_fragments`, `worker/sotto_worker.py:~3377`).

ARMS
  A  a linha MEDIDA colapsa (2 palavras repetidas)
  B  UMA palavra repetida e' FALA e sobrevive (`nao nao e' isso`)
  C  a repeticao mais LONGA ganha (colapsa o rabo inteiro, nao so' 2)
  D  repeticao NAO adjacente nao se toca
  E  integracao: os pares de fragmentos MEDIDOS, por `join_fragments`, dao a
     linha curada -- o oraculo le o ficheiro VIVO, nao uma copia da regra
  F  idempotente
  G  o texto do RUN e o do `--selftest` passam pela MESMA cura (as tres
     montagens de texto do ficheiro)

BRACO NEGATIVO (`--neg-arm`): uma copia do worker com
`SEAM_REPEAT_MIN_WORDS = 1` -- o mutante que trata fala legitima como artefacto.
A arm B tem de ficar RED nessa copia, senao o oraculo nao estava a medir a regra.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "..", "worker", "sotto_worker.py")

#: OS FRAGMENTOS MEDIDOS, verbatim do run `SOTTO_FILE_TAP` de 2026-11-02.
MEASURED = [
    ("caramba", False),
    ("tem", False),
    ("umas", False),
    ("tem umas", False),
    ("youtuber que", False),
    ("elas só", False),
    ("são sapadas", False),
    ("mesmo não", False),
    ("é", False),
]
MEASURED_LINE = "caramba tem umas youtuber que elas só são sapadas mesmo não é"
MEASURED_DUP = "caramba tem umas tem umas youtuber que elas só são sapadas mesmo não é"


def load(path=WORKER):
    spec = importlib.util.spec_from_file_location("sotto_worker_dedup", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    w = load()
    f = w.dedup_seam_repeat
    checks = []

    a = f(MEASURED_DUP)
    checks.append(("A", a == MEASURED_LINE, a))

    b = f("nao nao é isso")
    checks.append(("B", b == "nao nao é isso", b))

    c = f("e eu quero que a legenda a legenda apareça")
    checks.append(("C", c == "e eu quero que a legenda apareça", c))

    d = f("a b c x a b c")
    checks.append(("D", d == "a b c x a b c", d))

    e = w.join_fragments(MEASURED)
    checks.append(("E", e == MEASURED_LINE, e))

    base = f(MEASURED_DUP)
    checks.append(("F", f(base) == base, f(base)))

    src = open(WORKER, encoding="utf-8").read()
    g = ("dedup_seam_repeat(asr.detok(asr.labels))" in src
         and src.count("dedup_seam_repeat(") >= 4)
    checks.append(("G", g, "dedup_seam_repeat call sites=%d" % src.count("dedup_seam_repeat(")))

    for name, ok, val in checks:
        print("%s %s %r" % (name, "PASS" if ok else "FAIL", val))
    ok = all(c[1] for c in checks)
    print("VERDICT:", "GREEN" if ok else "RED")
    return 0 if ok else 1


def neg_arm():
    text = open(WORKER, encoding="utf-8", newline="").read()
    needle = "SEAM_REPEAT_MIN_WORDS = 2"
    if needle not in text:
        print("NEG-ARM FAIL: a constante nao esta' no worker")
        return 1
    mutant = text.replace(needle, "SEAM_REPEAT_MIN_WORDS = 1", 1)
    fd, tmp = tempfile.mkstemp(prefix="_mutant_dedup_", suffix=".py",
                               dir=os.path.dirname(os.path.abspath(WORKER)))
    os.close(fd)
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(mutant)
    try:
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", tmp],
                              capture_output=True, text=True)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    caught = proc.returncode != 0 and "B FAIL" in (proc.stdout or "")
    print("NEG-ARM mutant rc=%d caught=%s" % (proc.returncode, caught))
    for ln in (proc.stdout or "").splitlines():
        if ln.startswith("B "):
            print("  ", ln)
    print("NEG-ARM PASS" if caught else "NEG-ARM FAIL")
    # O `:expectred` da bateria exige rc=1 quando o mutante APANHADO: o passo
    # negativo PASSA com um RED (o defeito foi nomeado), nao com um zero.
    return 1 if caught else 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--neg-arm" in argv:
        raise SystemExit(neg_arm())
    path = WORKER
    for i, a in enumerate(argv):
        if a == "--worker":
            path = argv[i + 1]
        elif a.startswith("--worker="):
            path = a.split("=", 1)[1]
    if path != WORKER:
        # a copia do mutante: julga-se o `dedup_seam_repeat` DELA.
        w = load(path)
        ok_b = w.dedup_seam_repeat("nao nao é isso") == "nao nao é isso"
        ok_a = w.dedup_seam_repeat(MEASURED_DUP) == MEASURED_LINE
        print("A %s" % ("PASS" if ok_a else "FAIL"))
        print("B %s" % ("PASS" if ok_b else "FAIL"))
        ok = ok_a and ok_b
        print("VERDICT:", "GREEN" if ok else "RED")
        raise SystemExit(0 if ok else 1)
    raise SystemExit(main())
