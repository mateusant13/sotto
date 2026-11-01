"""A LEGENDA NAO RECUA NO TEMPO -- o instrumento da queixa de 2026-10-30.

A queixa do dono, verbatim: *"a legenda nao ta sincronizada direito. e parece
que repete a legenda de instantes atras no ao vivo, depois desbuga, e mostra ao
vivo"*.

O que este oraculo mede, e nada mais:

  ARMS DE REGRA (puros, sem app): `youtube_monotonic.decide` nunca serve um
  instante atras do chao, e `advance` so' desce o chao num seek a serio.

  ARM DE REPLAY (o log real): as linhas `YOUTUBE_CAPTION` de
  `_main/webview-run.log` sao corridas pela regra. A regra ANTIGA (servir
  sempre a leitura do relogio) tem de produzir recuos; a regra NOVA tem de
  produzir ZERO. Os dois numeros sao re-medidos a cada corrida -- nenhum e'
  citado de memoria.

  ARM DE LIGACAO (o codigo vivo): `sotto_webview.py` e' lido por AST -- os
  dois ramos que escolhem a cue por um relogio tem de passar por `_yt_decide`
  ANTES de `cue_at`, e os tres pontos de servico tem de subir o chao. Um
  comentario que diga a regra nao conta.

Exit: 0 = o que a ordem pede esta' medido; 1 = recua; 2 = nao ha medicao.
"""
# NO-BUG: instrumento da queixa do dono de 2026-10-30 (*"a legenda ... repete a
# legenda de instantes atras no ao vivo"*). MEDIDO no log dele: 129 das 2126
# linhas `YOUTUBE_CAPTION` serviam uma cue ANTERIOR a anterior, ate' 359 s
# atras, e a cue `start=34.239` foi servida tres vezes em 24 s. A regra antiga
# nesta mesma arvore recua 157 vezes (pior 310,68 s); a nova recua 0. Sem este
# braco, "a legenda nao recua" seria uma afirmacao e nao uma medicao.
from __future__ import annotations

import argparse
import ast
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WEBVIEW = os.path.join(REPO, "app", "webview")
MONO = os.path.join(WEBVIEW, "youtube_monotonic.py")
SHELL = os.path.join(WEBVIEW, "sotto_webview.py")
LOG = os.path.join(HERE, "webview-run.log")

if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

#: `cue=<start> t=<clock>` -- so' o ramo painted-other-track poe a cue START e a
#: leitura do RELOGIO em campos separados. O ramo `hit` poe o INDICE em `cue` e
#: o inicio da cue em `t`; sao duas formas e nao uma.
OTHER = re.compile(
    r"^(\S+ \S+) sotto: YOUTUBE_CAPTION video_id=(\S+) cue=([\d.]+) "
    r"t=([\d.]+) track=\S+ text=.*why=painted-other-track$")
HIT = re.compile(
    r"^(\S+ \S+) sotto: YOUTUBE_CAPTION video_id=(\S+) cue=\S+ "
    r"t=([\d.]+) track=\S+ words=\d+ text=")


def _load_module(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# ARM 1..6 -- a regra pura
# --------------------------------------------------------------------------
def arm_rule(mono):
    out = []
    # 1. nada servido ainda: serve a leitura tal e qual.
    s, f = mono.decide(10.0, None)
    out.append(("arm1-nothing-served", s == 10.0 and f == 10.0,
                "decide(10,None)=(%r,%r)" % (s, f)))
    # 2. adiantado: serve e o chao sobe.
    s, f = mono.decide(50.0, 40.0)
    out.append(("arm2-forward", s == 50.0 and f == 50.0,
                "decide(50,40)=(%r,%r)" % (s, f)))
    # 3. RELOGIO CONGELADO/ATRASADO: a leitura esta' atras do chao. Este e' o
    #    defeito do dono e nunca pode servir o valor atrasado.
    s, f = mono.decide(34.2, 74.7)
    out.append(("arm3-behind-floor-held", s == 74.7,
                "decide(34.2, floor=74.7) serviu %r (esperado 74.7)" % (s,)))
    # 4. O JITTER MEDIDO do relogio: salto de 5 s para tras (1175 -> 1170) com
    #    o video em ~1170 -- NAO e' seek, e' leitura. Tem de segurar o chao.
    s, f = mono.decide(1170.0, 1175.0)
    out.append(("arm4-clock-jitter-held", s == 1175.0,
                "decide(1170, floor=1175) serviu %r (o jitter de 5 s medido "
                "no log)" % (s,)))
    # 5. A PINTURA num seek a serio (salta 60 s para tras) DESCE o chao.
    f = mono.advance(74.7, 10.0)
    out.append(("arm5-paint-seek-descends", f == 10.0,
                "advance(74.7, 10.0)=%r (esperado 10.0)" % (f,)))
    # 6. A PINTURA a repetir um cue um pouco atras NAO desce o chao.
    f = mono.advance(74.7, 73.0)
    out.append(("arm6-paint-jitter-holds", f == 74.7,
                "advance(74.7, 73.0)=%r (esperado 74.7)" % (f,)))
    # 7. A PINTURA a avancar sobe o chao.
    f = mono.advance(40.0, 50.0)
    out.append(("arm7-paint-advances", f == 50.0,
                "advance(40,50)=%r" % (f,)))
    return out


# --------------------------------------------------------------------------
# ARM 8 -- replay do LOG REAL, com as duas regras
# --------------------------------------------------------------------------
def read_log(path):
    """[(video_id, kind, a, b)] na ordem do ficheiro.

    `kind="clock"` -> `a` e' o INICIO da cue servida, `b` a leitura do relogio.
    `kind="paint"` -> `a` e' o inicio da cue que o player pinta, `b` None.

    O `video_id` viaja porque o log cobre MUITOS videos: cada um recomeca em
    t=0, e reiniciar o tempo de um video novo nao e' um recuo -- e' uma nova
    linha temporal. Sem esta coluna o instrumento acusava 47 "recuos" que
    eram so' mudancas de video.
    """
    rows = []
    try:
        fh = io.open(path, encoding="utf-8", errors="replace")
    except OSError:
        return rows
    with fh:
        for line in fh:
            line = line.rstrip("\n")
            m = OTHER.match(line)
            if m:
                rows.append((m.group(2), "clock", float(m.group(3)),
                             float(m.group(4))))
                continue
            m = HIT.match(line)
            if m:
                rows.append((m.group(2), "paint", float(m.group(3)), None))
    return rows


def replay(rows, mono, rule, seek_back=2.0):
    """Conta os recuos das duas regras sobre as MESMAS linhas.

    `rule="old"`  -- o que `sotto_webview.py` fazia: servir sempre a leitura.
    `rule="new"`  -- `youtube_monotonic.decide`.

    Devolve `(back_via_clock, back_via_paint, seeks, served, worst)`.

    `back_via_clock` e' o defeito: o ecra recua por causa de uma LEITURA do
    relogio. Tem de ser 0 na regra nova. `back_via_paint` sao recuos
    declarados pela PINTURA -- um seek a serio -- e sao legitimos; contam-se
    para o relatorio, nunca como falha.
    """
    floor = None
    shown = None
    vid = None
    back_clock = back_paint = seeks = served = 0
    worst = 0.0
    for row_vid, kind, a, b in rows:
        if row_vid != vid:
            vid = row_vid
            floor = shown = None
        if kind == "paint":
            if shown is not None and a < shown - seek_back:
                # A PINTURA recuou de vez: o ecra VAI para tras, e e' um seek
                # a serio. `shown` tem de descer com ele -- senao as leituras
                # seguintes nessa linha temporal contavam como recuo do
                # relogio, que e' uma classe diferente e nao e' o defeito.
                seeks += 1
                back_paint += 1
                shown = a
            else:
                shown = a if shown is None else max(shown, a)
            floor = mono.advance(floor, a)
            continue
        if rule == "new":
            used, floor = mono.decide(b, floor)
        else:
            used = b
            floor = mono.advance(floor, used)
        served += 1
        if shown is not None and used < shown - 0.05:
            back_clock += 1
            worst = max(worst, shown - used)
        shown = used if shown is None else max(shown, used)
    return back_clock, back_paint, seeks, served, worst


# --------------------------------------------------------------------------
# ARM 9 -- a LIGACAO no codigo vivo, por AST
# --------------------------------------------------------------------------
def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def arm_wiring(path):
    with io.open(path, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_youtube":
            fn = node
            break
    if fn is None:
        return [("arm9-wiring", False, "_youtube nao existe em %s" % path)]
    calls = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            calls.append((getattr(node, "lineno", 0), _dotted(node.func)))
    decides = [ln for ln, name in calls if name == "self._yt_decide"]
    advances = [ln for ln, name in calls if name == "self._yt_advance"]
    cueat = [ln for ln, name in calls if name.endswith("cue_at")]
    out = []
    out.append(("arm9-decide-called-twice", len(decides) >= 2,
                "_yt_decide em _youtube: %d chamada(s) (os dois ramos que "
                "escolhem a cue por um relogio)" % len(decides)))
    out.append(("arm9-advance-called-thrice", len(advances) >= 3,
                "_yt_advance em _youtube: %d chamada(s) (pintado, "
                "painted-other-track, has-cue)" % len(advances)))
    ok = False
    why = "nenhum cue_at depois de um _yt_decide"
    if decides and cueat:
        first = min(decides)
        for ln in cueat:
            if ln > first:
                ok = True
                why = "_yt_decide@%d antes de cue_at@%d" % (first, ln)
                break
    out.append(("arm9-decide-precedes-cue", ok, why))
    out.append(("arm9-module-imported", "youtube_monotonic" in src,
                "sotto_webview.py importa youtube_monotonic: %s"
                % ("sim" if "youtube_monotonic" in src else "NAO")))
    return out


# --------------------------------------------------------------------------
# O MUTANTE do braco negativo: a regra ANTIGA, escrita de proposito.
# --------------------------------------------------------------------------
MUTANT = '''\
FREEZE_EPS_S = 0.05
SEEK_BACK_S = 2.0


def decide(now_t, floor, freeze_eps=FREEZE_EPS_S):
    """A REGRA ANTIGA: serve a leitura do relogio, aconteca o que acontecer."""
    if now_t is None:
        return None, floor
    return float(now_t), float(now_t)


def advance(floor, position, seek_back=SEEK_BACK_S):
    if position is None:
        return floor
    try:
        pos = float(position)
    except (TypeError, ValueError):
        return floor
    if floor is None or pos > float(floor):
        return pos
    return floor
'''


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--neg-arm", action="store_true",
                    help="prova que o instrumento APANHA o defeito: com a "
                         "regra antiga o replay TEM de acusar recuos. "
                         "rc 1 e' o PASS aqui.")
    ap.add_argument("--log", default=LOG)
    args = ap.parse_args(argv)

    for path in (MONO, SHELL):
        if not os.path.exists(path):
            print("YOUTUBE-MONOTONIC NO-VERDICT -- falta %s" % path)
            return 2

    rows = read_log(args.log)
    if not rows:
        print("YOUTUBE-MONOTONIC NO-VERDICT -- %s sem linhas YOUTUBE_CAPTION"
              % os.path.basename(args.log))
        return 2

    if args.neg_arm:
        tmpd = tempfile.mkdtemp(prefix="ytmono-",
                                dir=os.environ.get("TMPDIR") or None)
        try:
            mpath = os.path.join(tmpd, "youtube_monotonic_old.py")
            with io.open(mpath, "w", encoding="utf-8") as fh:
                fh.write(MUTANT)
            old = _load_module(mpath, "youtube_monotonic_old")
            b_clock, _, _, n, worst = replay(rows, old, "old")
            if b_clock <= 0:
                print("NEG-ARM FAIL -- a regra ANTIGA nao produziu recuo "
                      "nenhum em %d linha(s): o instrumento nao tem dentes"
                      % n)
                return 1
            print("NEG-ARM PASS -- RED as designed: a regra ANTIGA recuou o "
                  "ecra %d vez(es) em %d linha(s), pior %.2f s"
                  % (b_clock, n, worst))
            return 1
        finally:
            shutil.rmtree(tmpd, ignore_errors=True)

    mono = _load_module(MONO, "youtube_monotonic_live")
    results = arm_rule(mono)
    results += arm_wiring(SHELL)

    b_old, _, _, n, worst_old = replay(rows, mono, "old")
    b_new, b_paint, seeks, _, worst_new = replay(rows, mono, "new")
    results.append(("arm8-replay-no-clock-recoil", b_new == 0,
                    "replay de %d linha(s): regra ANTIGA recua %d (pior "
                    "%.2f s), regra NOVA recua %d%s"
                    % (n, b_old, worst_old, b_new,
                       (" (pior %.2f s)" % worst_new) if b_new else "")))
    results.append(("arm8-old-rule-did-recoil", b_old >= 10,
                    "a regra antiga tem de recuar em >=10 linhas para o arm8 "
                    "valer: recuou %d" % b_old))
    results.append(("arm8-seeks-kept", b_paint >= 0,
                    "recuos declarados pela PINTURA (seeks, legitimos): %d"
                    % b_paint))

    failed = 0
    for name, ok, detail in results:
        print("%-4s %-38s %s" % ("PASS" if ok else "FAIL", name, detail))
        if not ok:
            failed += 1
    total = len(results)
    if failed:
        print("YOUTUBE-MONOTONIC VERDICT RED -- %d PASS / %d FAIL"
              % (total - failed, failed))
        return 1
    print("YOUTUBE-MONOTONIC VERDICT GREEN -- %d PASS / 0 FAIL "
          "(recuos do relogio: antiga %d, nova %d; seeks pela pintura: %d)"
          % (total, b_old, b_new, b_paint))
    return 0


if __name__ == "__main__":
    sys.exit(main())
