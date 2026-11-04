#!/usr/bin/env python3
# NO-BUG: A REPETICAO NO SEAM DO CHUNK -- medida, e a cura provada num so' lugar. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
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

#: AS DUAS LINHAS QUE A REGRA DEIXAVA PASSAR, verbatim do `CAPTION_APPLIED` da
#: sessao VIVA do dono (2026-11-03, 11:39, instancia pid 55456; 2 de 62 linhas
#: com repeticao). A comparacao exacta nunca casava a primeira -- o run repetido
#: comeca em `Sempre` (maiuscula de inicio de linha) e volta como `sempre` -- e o
#: artefacto CRESCE (`A`, `A+B`, `A+B+C`), por isso uma passagem so' ainda
#: deixava uma copia.
LIVE_GROWING_DUP = ("Sempre falei do sempre falei do cenário "
                    "sempre falei do cenário político.")
LIVE_GROWING_LINE = "Sempre falei do cenário político."
LIVE_COMMA_DUP = "Acompanha vam, e me acompanha vam, e me acompanha há."
LIVE_COMMA_LINE = "Acompanha vam, e me acompanha há."


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

    h = f(LIVE_GROWING_DUP)
    checks.append(("H", h == LIVE_GROWING_LINE, h))

    i = f(LIVE_COMMA_DUP)
    checks.append(("I", i == LIVE_COMMA_LINE, i))

    # J: O PARCIAL. `line()` passa por `join_fragments` (que dedupa); o parcial
    # vai a' tela pelo `proven_text`, que junta por conta propria. Medido na
    # sessao de 11:43: 5 de 35 linhas desta instancia ainda repetiam, e todas
    # passam limpas pela regra -- era a CHAMADA que faltava.
    lf = w.LineFormer(min_chars=1, emit_partial=True)
    evs = []
    evs += lf.push("posi a estava pedindo que posi a estava pedindo", start=0.0, end=1.0)
    evs += lf.push("que eu fim", start=1.0, end=2.0)
    evs += lf.push("", start=2.0, end=2.0)
    bad = [e["text"] for e in evs if f(e["text"]) != e["text"]]
    checks.append(("J", not bad, bad or "nenhum parcial repetido"))

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
                              capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
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

    # SEGUNDO MUTANTE: a NORMALIZACAO. Sem `casefold`/sem tirar a pontuacao o
    # run que comeca em `Sempre` (ou em `vam,`) nunca casa com a copia, e a
    # linha sai repetida -- e' exactamente o que o log do dono publicou.
    needle2 = "    return word.strip('.,;:!?\\u00ab\\u00bb\"\\'()[]-').casefold()"
    caught2 = False
    if needle2 in text:
        mutant2 = text.replace(needle2, "    return word", 1)
        fd2, tmp2 = tempfile.mkstemp(prefix="_mutant_seamkey_", suffix=".py",
                                     dir=os.path.dirname(os.path.abspath(WORKER)))
        os.close(fd2)
        with open(tmp2, "w", encoding="utf-8", newline="") as fh:
            fh.write(mutant2)
        try:
            proc2 = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", tmp2],
                                   capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        finally:
            try:
                os.unlink(tmp2)
            except OSError:
                pass
        caught2 = proc2.returncode != 0 and "H FAIL" in (proc2.stdout or "")
        print("NEG-ARM seam-key mutant rc=%d caught=%s" % (proc2.returncode, caught2))
        for ln in (proc2.stdout or "").splitlines():
            if ln.startswith("H "):
                print("  ", ln)
    else:
        print("NEG-ARM seam-key mutant: ANCORA AUSENTE no worker")

    # TERCEIRO MUTANTE: a CHAMADA no caminho PARCIAL. Sem ela o `line()` continua
    # curado e o texto que o dono VE nao.
    needle3 = "            estavel = dedup_seam_repeat(estavel)"
    caught3 = False
    if needle3 in text:
        mutant3 = text.replace(needle3, "            pass", 1)
        fd3, tmp3 = tempfile.mkstemp(prefix="_mutant_partial_", suffix=".py",
                                     dir=os.path.dirname(os.path.abspath(WORKER)))
        os.close(fd3)
        with open(tmp3, "w", encoding="utf-8", newline="") as fh:
            fh.write(mutant3)
        try:
            proc3 = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", tmp3],
                                   capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        finally:
            try:
                os.unlink(tmp3)
            except OSError:
                pass
        caught3 = proc3.returncode != 0 and "J FAIL" in (proc3.stdout or "")
        print("NEG-ARM partial mutant rc=%d caught=%s" % (proc3.returncode, caught3))
        for ln in (proc3.stdout or "").splitlines():
            if ln.startswith("J "):
                print("  ", ln)
    else:
        print("NEG-ARM partial mutant: ANCORA AUSENTE no worker")
    caught = caught and caught2 and caught3
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
        ok_h = w.dedup_seam_repeat(LIVE_GROWING_DUP) == LIVE_GROWING_LINE
        lf2 = w.LineFormer(min_chars=1, emit_partial=True)
        e2 = []
        e2 += lf2.push("posi a estava pedindo que posi a estava pedindo", start=0.0, end=1.0)
        e2 += lf2.push("que eu fim", start=1.0, end=2.0)
        ok_j = not [e for e in e2 if w.dedup_seam_repeat(e["text"]) != e["text"]]
        print("A %s" % ("PASS" if ok_a else "FAIL"))
        print("B %s" % ("PASS" if ok_b else "FAIL"))
        print("H %s" % ("PASS" if ok_h else "FAIL"))
        print("J %s" % ("PASS" if ok_j else "FAIL"))
        ok = ok_a and ok_b and ok_h and ok_j
        print("VERDICT:", "GREEN" if ok else "RED")
        raise SystemExit(0 if ok else 1)
    raise SystemExit(main())
