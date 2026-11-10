#!/usr/bin/env python
"""Portao do `audio_back_step`: "o audio voltou e nada acontece" tem duas linhas.

CARD DO DONO (verbatim): *"audio volta e nada acontece"*. O worker ja' publicava
`TAP_IDLE`/`TAP_STALLED` quando o audio SUMIA e `WORKER_RESUMED` quando o PARQUE
acabava; nenhuma das duas responde a pergunta dele -- **os blocos voltaram e a
legenda nao?** O par (blocos a subir, `captions` parado) nao era lido por linha
nenhuma, logo o sintoma era indistinguivel de um worker saudavel a transcrever
silencio.

O QUE ESTE ORACULO JULGA: a maquina PURA `worker.sotto_worker.audio_back_step`
(o chamador no laco de audio apenas passa os numeros) e o SITE de chamada, por
`ast` -- nada aqui abre dispositivo, toca audio ou precisa da tela do dono.

  A1 lacuna (`gap_s >= TAP_STALL_S`) fecha em `CAPTURE_SIGNAL_BACK` com os
     numeros do instante
  A2 a mesma lacuna nao re-arma a cada iteracao
  A3 dentro da graca, nada e' dito
  A4 graca vencida + legendas PARADAS -> `NO_CAPTION_AFTER_AUDIO_BACK`
  A5 graca vencida + legendas AVANCARAM -> silencio, e o estado morre
  A6 a linha do defeito sai UMA vez
  A7 `CAPTURE_SIGNAL_BACK` carrega `blocks=` e `captions=`
  A8 `NO_CAPTION_AFTER_AUDIO_BACK` carrega `blocks_delta=` e `captions=`
  A9 o limiar de lacuna E' o `TAP_STALL_S` do ficheiro (lido por `ast`)
  B  o SITE passa `now`, blocos, legendas e `now - stall_since`, e escreve a
     linha por `err(...)`

USO
  python _main/audio-back-detector-oracle.py            -> rc=0 quando passa
  python _main/audio-back-detector-oracle.py --neg-arm  -> muta o codigo numa
                                                           copia e exige rc=1
"""
import ast
import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

T0 = 1_000_000.0


def parse(src):
    tree = ast.parse(src)
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:                                 # noqa: BLE001
                pass
    return tree, consts


def load_namespace(src, path):
    """Executa a fonte num namespace proprio (o mutante nao polui `worker`)."""
    mod = types.ModuleType("audio_back_mutant")
    mod.__file__ = path
    exec(compile(src, path, "exec"), mod.__dict__)
    return mod


def run_arms(fn, src, tree, consts, say):
    """Roda A1-A9/B sobre a funcao e a fonte dadas. Devolve a lista de falhas."""
    fails = []
    stall_s = float(consts["TAP_STALL_S"])
    grace = float(consts["AUDIO_BACK_GRACE_S"])

    def check(name, ok, detail=""):
        if not ok:
            fails.append(name)
        say(name, ok, detail)

    st, line = fn(T0, 120, 4, stall_s + 4.0, None)
    check("A1", bool(line) and "CAPTURE_SIGNAL_BACK" in line, str(line))
    st2, line2 = fn(T0 + 0.1, 121, 4, 0.1, st) if st else (None, "sem estado")
    check("A2", line2 is None and st2 is not None, str(line2))
    _s3, line3 = fn(T0 + grace / 2.0, 200, 4, 0.1, st)
    check("A3", line3 is None, str(line3))
    st4, line4 = fn(T0 + grace + 1.0, 400, 4, 0.1, st)
    check("A4", bool(line4) and "NO_CAPTION_AFTER_AUDIO_BACK" in line4, str(line4))
    st5, line5 = fn(T0 + grace + 1.0, 400, 5, 0.1, st)
    check("A5", line5 is None and st5 is None, "%r %r" % (line5, st5))
    _s6, line6 = fn(T0 + grace + 2.0, 401, 4, 0.1, st4)
    check("A6", line6 is None, str(line6))
    check("A7", "blocks=120" in (line or "") and "captions=4" in (line or ""), str(line))
    check("A8", "blocks_delta=%d" % (400 - 120) in (line4 or "")
          and "captions=4" in (line4 or ""), str(line4))
    # A9 E' ESTRUTURAL, nao textual: um `in src` casava com o proprio comentario
    # que cita o limiar, e o mutante M3 (2,5 no lugar de `TAP_STALL_S`) passava
    # por causa disso -- medido no `--neg-arm` desta mesma rodada.
    cmp_ok = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) \
                and node.left.id == "gap_s" and len(node.comparators) == 1 \
                and isinstance(node.comparators[0], ast.Name) \
                and node.comparators[0].id == "TAP_STALL_S":
            cmp_ok = True
    check("A9", cmp_ok, "o limiar e' o TAP_STALL_S do ficheiro (por AST)")

    call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "audio_back_step":
            call = node
    if call is None:
        check("B", False, "nenhum sitio chama audio_back_step")
        check("B2", False, "sem sitio nao ha' linha")
    else:
        seg = ast.get_source_segment(src, call) or ""
        ok = "stall_since" in seg and "counters" in seg and "device_blocks" in seg
        check("B", ok, seg.replace("\n", " ")[:120])
        check("B2", "_back_line" in src and "err(" in src, "a linha sai por err(...)")
    return fails


def main(argv):
    say = lambda n, ok, d: print("  %-4s %s%s" % (n, "ok" if ok else "FAIL",
                                                 ("  " + str(d)) if d else ""))
    src = open(WORKER, "r", encoding="utf-8").read()
    tree, consts = parse(src)
    from worker.sotto_worker import audio_back_step

    if "--neg-arm" in argv:
        tmp = tempfile.mkdtemp(prefix="audio-back-neg-")
        path = os.path.join(tmp, "mutant.py")
        mutants = {
            "M1_graca_invertida": src.replace(
                "if now - back_watch['t'] < grace_s:",
                "if now - back_watch['t'] > 10 ** 9:"),
            "M2_nunca_compara_legenda": src.replace(
                "    if captions != back_watch['captions']:\n        return None, None\n", ""),
            "M3_limiar_proprio": src.replace(
                "if gap_s >= TAP_STALL_S:", "if gap_s >= 2.5:"),
            "M4_site_apagado": src.replace(
                "back_watch, _back_line = audio_back_step(", "back_watch, _back_line = (None, None); _unused("),
        }
        caught = 0
        for name, mutated in mutants.items():
            if mutated == src:
                print("  %-24s NOT-APPLIED (a ancora nao existe)" % name)
                continue
            open(path, "w", encoding="utf-8").write(mutated)
            mtree, mconsts = parse(mutated)
            try:
                mod = load_namespace(mutated, path)
                mfails = run_arms(mod.audio_back_step, mutated, mtree, mconsts,
                                  lambda *a, **k: None)
            except Exception:                                 # noqa: BLE001
                mfails = ["crash"]
            if mfails:
                caught += 1
                print("  %-24s CAUGHT (%s)" % (name, ",".join(mfails)))
            else:
                print("  %-24s NOT-CAUGHT" % name)
        shutil.rmtree(tmp, ignore_errors=True)
        total = len(mutants)
        print("NEG-ARM: %s -- %d/%d mutantes apanhados"
              % ("PASS" if caught == total else "FAIL", caught, total))
        return 0 if caught == total else 1

    print("AUDIO-BACK-DETECTOR")
    fails = run_arms(audio_back_step, src, tree, consts, say)
    print("")
    if fails:
        print("VERDICT: FAIL -- %s" % "; ".join(fails))
        return 1
    print("VERDICT: PASS -- 11 arm(s), 0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
