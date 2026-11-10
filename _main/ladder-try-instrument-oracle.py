#!/usr/bin/env python
"""O portao do `LADDER_TRY`: o custo de ABRIR cada rung tem uma linha, com ms.

PORQUE ESTE ORACULO EXISTE (medido 2026-11-10, log do dono pid 52792): entre
`model-loaded` (21:22:33.014) e `capture-started` (21:22:56.047) passaram **23 s
sem UMA linha**, com `STATUS_APPLIED text=device` as 21:22:50. O card do dono
("o arranque demora DEMAIS a responder") nao tinha dono porque a escada de
dispositivos nao publicava custo nenhum. `CAPTURE_FIRST_PICK` ja' publicava
`probe_ms` do CENSO; o que faltava era o custo de ABRIR cada candidato.

O QUE ELE JULGA, e nao e' o texto: ele EXECUTA `worker.sotto_worker.ladder_try_line`
(a funcao PURA que o site de chamada usa) e exige as propriedades que fazem a
linha ser atribuivel. Abrir um dispositivo de verdade esta' fora de alcance de
uma lane (audio do dono: `MUST NOT` tocar), logo o portao mede a FUNCAO e o
SITE -- e o site tem de a chamar, senao a instrumentacao nao esta' ligada.

  A1  a linha nomeia o numero da tentativa e o total (`attempt=2/9`)
  A2  nomeia o candidato (`device='...'`) -- sem isto o ms nao tem dono
  A3  carrega `ms=` como INTEIRO, e o valor e' o que o chamador passou
  A4  `result=opened` quando abriu
  A5  `result=refused` quando o open levantou/recusou
  A6  `result=stopped` quando a corrida pediu para parar (tap None, sem erro)
  A7  `retries=` conta as tentativas gastas na espera de `DEVICE_IN_USE`
  A8  `api=` viaja quando o candidato a tem, e `api=None` quando nao tem
  A9  `ms` ARREDONDA para baixo: 0,9 ms e' `ms=0`, nunca 1 (um numero
      arredondado para cima mentiria sobre o piso)
  A10 `device` ausente (`None`) nao levanta -- um candidato sem nome e' um
      defeito do CENSO, e um instrumento que morre no defeito nao relata
  A11 o SITE de chamada em `worker/sotto_worker.py` chama esta funcao (por
      `ast`, com o no exato) e nao uma `%`-formatacao propria
  A12 o site carimba `_t_try` ANTES do laco de retry -- o `ms` mede a ABERTURA,
      nao tres voltas de espera de 1,5 s somadas ao final
  B   identidade: a mesma entrada da' a mesma linha (sem relogio dentro dela)

USO
  python _main/ladder-try-instrument-oracle.py            -> rc=0 quando passa
  python _main/ladder-try-instrument-oracle.py --neg-arm  -> muta o codigo numa
                                                             copia e exige rc=1
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FAILS = []


def check(name, ok, detail=""):
    if not ok:
        FAILS.append("%s%s" % (name, (": " + detail) if detail else ""))
    print("  %-8s %s%s" % (name, "ok" if ok else "FAIL", ("  " + detail) if detail else ""))


def load_fn():
    from worker.sotto_worker import ladder_try_line
    return ladder_try_line


def site_nodes(tree):
    """Todo `Call` cujo func e' `ladder_try_line`, com o segmento de fonte."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "ladder_try_line":
                out.append(node)
    return out


def run_arms():
    fn = load_fn()
    dev = {"name": "VoiceMeeter Input", "api": "wasapi",
           "endpoint_id": "{0.0.0.00000000}.{dead-beef}"}
    line = fn(2, 9, dev, 1743.7, 1, True, False)
    check("A1", "attempt=2/9" in line, line)
    check("A2", "VoiceMeeter Input" in line, line)
    check("A3", " ms=1743 " in line, line)
    check("A4", "result=opened" in line, line)
    check("A5", "result=refused" in fn(1, 3, dev, 200.0, 0, False, False), "refused")
    check("A6", "result=stopped" in fn(1, 3, dev, 5.0, 0, False, True), "stopped")
    check("A7", "retries=2" in fn(1, 3, dev, 3000.0, 2, True, False), "retries")
    check("A8", "api='wasapi'" in fn(1, 3, dev, 1.0, 0, True, False)
          and "api=None" in fn(1, 3, {"name": "x"}, 1.0, 0, True, False), "api")
    check("A9", "ms=0 " in fn(1, 2, dev, 0.9, 0, True, False),
          fn(1, 2, dev, 0.9, 0, True, False))
    try:
        nameless = fn(1, 2, None, 4.0, 0, True, False)
        ok = "device=None" in nameless and "ms=4 " in nameless
        detail = nameless
    except Exception as exc:                                  # noqa: BLE001
        ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    check("A10", ok, detail)
    check("B", line == fn(2, 9, dev, 1743.7, 1, True, False), "identidade")


def run_site_arms():
    src = open(WORKER, "r", encoding="utf-8").read()
    tree = ast.parse(src)
    nodes = site_nodes(tree)
    check("A11", len(nodes) == 1, "%d sitio(s) de chamada" % len(nodes))
    if nodes:
        pos = nodes[0].lineno
        seg = ast.get_source_segment(src, nodes[0]) or ""
        check("A12", "_t_try" in seg, "o site passa o relogio da abertura")
        # `_t_try` tem de ser carimbado ANTES do laco de retry do rung.
        src_lines = src.splitlines()
        t_try = None
        for i, ln in enumerate(src_lines[:pos], start=1):
            if "_t_try = time.monotonic()" in ln:
                t_try = i
        loop_line = None
        for node in ast.walk(tree):
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name) \
                    and node.target.id == "retry":
                if loop_line is None or abs(node.lineno - pos) < abs(loop_line - pos):
                    loop_line = node.lineno
        check("A12b", t_try is not None and loop_line is not None and t_try < loop_line,
              "carimbo=%s laco=%s" % (t_try, loop_line))


def neg_arm():
    """Muta a instrumentacao numa COPIA e exige que o portao a apanhe."""
    import importlib
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="ladder-try-neg-")
    dst = os.path.join(tmp, "sotto_worker.py")
    shutil.copyfile(WORKER, dst)
    src = open(dst, "r", encoding="utf-8").read()
    mutants = 0
    caught = 0

    def expect(name, mutated_src, arm):
        nonlocal mutants, caught
        mutants += 1
        open(dst, "w", encoding="utf-8").write(mutated_src)
        # Carrega o mutante por caminho, sem poluir `worker.sotto_worker`.
        import types
        mod = types.ModuleType("mutant_worker")
        mod.__file__ = dst
        try:
            exec(compile(mutated_src, dst, "exec"), mod.__dict__)
            f = mod.ladder_try_line
            line = f(2, 9, {"name": "VoiceMeeter Input", "api": "wasapi"}, 1743.7, 1, True, False)
            hit = {
                "M1": "ms=" not in line,
                "M2": "device=" not in line,
                "M3": "attempt=2/9" not in line,
                "M4": "result=refused" in line,
            }[arm]
        except Exception:                                     # noqa: BLE001
            hit = True
        if hit:
            caught += 1
            print("  %-4s CAUGHT" % name)
        else:
            print("  %-4s NOT-CAUGHT" % name)

    m1 = src.replace('% (int(attempt_no), int(of), (dev or {}).get("name"),\n'
                     '               (dev or {}).get("api"), int(ms), int(retries), result))',
                     '% (int(attempt_no), int(of), (dev or {}).get("name"),\n'
                     '               (dev or {}).get("api"), 0, int(retries), result))')
    expect("M1", m1, "M1")
    m2 = src.replace('device=%r api=%r', 'api=%r')
    expect("M2", m2, "M2")
    m3 = src.replace('attempt=%d/%d', 'attempt=%d')
    expect("M3", m3, "M3")
    m4 = src.replace('result = "stopped" if stopped else ("opened" if opened else "refused")',
                     'result = "refused"')
    expect("M4", m4, "M4")
    shutil.rmtree(tmp, ignore_errors=True)
    print("NEG-ARM: PASS -- %d/%d mutantes apanhados" % (caught, mutants))
    return 0 if caught == mutants else 1


def main(argv):
    if "--neg-arm" in argv:
        return neg_arm()
    print("LADDER-TRY-INSTRUMENT")
    run_arms()
    run_site_arms()
    print("")
    if FAILS:
        print("VERDICT: FAIL -- %d arm(s): %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("VERDICT: PASS -- %d arm(s), 0 failure(s)" % 12)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
