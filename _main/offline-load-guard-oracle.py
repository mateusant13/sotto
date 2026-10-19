"""PORTAO DA GUARDA DE CARGA DA FASE B.

O QUE ESTA GUARDA FECHA
=======================
O dono, 2026-10-18, verbatim: *"processar depois quando e' seguro e nao travar o
pc do usuario."* A segunda metade da frase e' uma CONDICAO, e ate agora nao tinha
instrumento: `_main/multivoice-offline.py` carregava os dois modelos (135 MB) sem
perguntar se havia folga.

`worker/_cpu-load` mede a folga. Este script e' o primeiro consumidor dele. Um
instrumento sem consumidor e' um sinal sem consumidor -- o mesmo buraco que a
Fase A teve com o audio (§7.4), e que nao se repete.

A PROPRIEDADE QUE ESTE PORTAO PROVA, E QUE E' A DIFICIL
=====================================================
**A recusa tem de acontecer ANTES de o modelo ser carregado.** Recusar depois de
pagar 135 MB e' pagar para descobrir que nao se pode. Isso mede-se assim:

  - `main()` com a carga recusada tem de devolver rc=4 e o stub do carregador
    NAO pode ter sido chamado;
  - e `main()` com `--ignore-load` tem de CHAMAR o stub.

O segundo check e' o que torna o primeiro honesto. "O stub nao foi chamado" passa
igualmente se o stub nunca pudesse ser chamado -- por um `return` a mais, por um
`if` malposto, por um typo. Um porta que passa por nao fazer nada e' o pior
dos dois: parece verde e nao mede nada.

O `--neg-arm`
=============
Poe a guarda a `return 0` numa copia do ficheiro -- o estado de antes da feature.
A recusa tem de DESAPARECER e o porta tem de reprovar. Uma guarda que nao sabe
dizer NAO esta a dar a sensacao de estar a resolver o problema.
"""
import argparse
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(HERE, "multivoice-offline.py")

FAILURES = []
CHECKS = [0]


def check(ok, label, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(label)
    detail = detail if isinstance(detail, str) else repr(detail)
    print("   [%s] %s%s" % ("ok" if ok else "XX", label,
                            ("  -- " + detail) if detail else ""))
    return ok


def load_module(path=TARGET, name="_mv_offline_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeCpu(object):
    """Substitui `_cpu-load`: decide o veredicto sem medir a maquina."""

    def __init__(self, publishable, why="carga 80%, 9 de 20 nucleos livres"):
        self.publishable = publishable
        self.why = why
        self.calls = 0

    def load_ok(self, interval=0.6):
        self.calls += 1
        return self.publishable, self.why


def write_clip(path, seconds=0.6, rate=16000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neg-arm", action="store_true",
                    help="guarda a return 0: a recusa tem de desaparecer")
    args = ap.parse_args(argv)

    neg = bool(args.neg_arm)
    tmp = tempfile.mkdtemp(prefix="guard-", dir="I:\\cc-tmp")
    try:
        return _run(args, tmp, neg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(args, tmp, neg):
    print("=" * 78)
    print("PORTAO DA GUARDA DE CARGA DA FASE B%s"
          % ("   BRAACO NEGATIVO" if neg else ""))
    print("=" * 78)

    clip = write_clip(os.path.join(tmp, "mv-1900000000000.wav"))
    work = TARGET
    if neg:
        src = open(TARGET, "r", encoding="utf-8").read()
        mutated = src.replace("    return RC_SEM_FOLGA, why",
                              "    return 0, why  # MUTANTE")
        if mutated == src:
            print("   [XX] MUTANTE NAO APLICOU -- o porta nao o veria")
            return 1
        # A copia vive em `I:\cc-tmp`, portanto o `HERE`/`ROOT` que ela calcula
        # a partir de `__file__` apontariam para o temporario e `import
        # speaker_sidecar` rebentaria ANTES de o mutante ser testado. Um neg
        # arm que morre a carregar o modulo nao testou a guarda: testou o
        # caminho. Os caminhos passam a ser os reais.
        real_here = HERE.replace("\\", "\\\\")
        real_root = ROOT.replace("\\", "\\\\")
        for old, new in (
                ("HERE = os.path.dirname(os.path.abspath(__file__))",
                 'HERE = "%s"' % real_here),
                ("ROOT = os.path.dirname(HERE)",
                 'ROOT = "%s"' % real_root)):
            if old in mutated:
                mutated = mutated.replace(old, new)
        work = os.path.join(tmp, "mutated-offline.py")
        with open(work, "w", encoding="utf-8") as fh:
            fh.write(mutated)

    off = load_module(work)

    # ---- A GUARDA, ISOLADA ------------------------------------------------
    print("\nA FUNCAO DA GUARDA, sem maquina nenhuma")
    rc_ok, why_ok = off.guard(FakeCpu(True), False)
    check(rc_ok == 0, "com folga passa e devolve a frase da carga", why_ok)
    check("nucleos livres" in why_ok,
          "e a frase traz o numero, nao um 'ok'", why_ok)

    rc_no, why_no = off.guard(FakeCpu(False, "NENHUM nucleo livre (20/20)"), False)
    if neg:
        check(rc_no == 0,
              "BRACO NEGATIVO: sem a guarda a recusa DESAPARECE",
              "rc=%d -- o porta tem de reprovar isto" % rc_no)
    else:
        check(rc_no == off.RC_SEM_FOLGA,
              "sem nucleo livre RECUSA com rc proprio",
              "rc=%d (esperado %d)" % (rc_no, off.RC_SEM_FOLGA))
        check(rc_no != 3,
              "e o rc da recusa e' DISTINTO do rc de 'nenhum clip'",
              "rc=%d vs 3" % rc_no)
        check("NENHUM nucleo" in why_no,
              "e o motivo da recusa vai no payload, nao se perde", why_no)

        rc_ig, why_ig = off.guard(None, True)
        check(rc_ig == 0 and "DESLIGADA" in why_ig,
              "--ignore-load passa E DIZ QUE PASSOU", why_ig)

        rc_nl, why_nl = off.guard(None, False)
        check(rc_nl == 0 and "NAO LIDA" in why_nl,
              "modulo ilegivel NAO e' recusado: recusar por nao saber seria "
              "mentir sobre a maquina", why_nl)

    # ---- A ORDEM: A RECUSA ANTES DO MODELO --------------------------------
    print("\nA ORDEM, que e' a propriedade dificil")
    loads = []

    def spy(*a, **k):
        loads.append(1)
        raise AssertionError("CARREGOU OS MODELOS")

    real_loader = off.S._load_sherpa_diarizer
    real_cpu = off.load_cpu_module
    try:
        off.load_cpu_module = lambda: FakeCpu(False, "NENHUM nucleo livre (20/20)")
        off.S._load_sherpa_diarizer = spy
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        # O mutante CHAMA o carregador, e o spy levanta. Isso e' o achado, nao
        # uma falha do porta: por isso e' apanhado aqui e julgado abaixo.
        try:
            rc = off.main([clip])
            raised = None
        except AssertionError as exc:
            rc, raised = None, str(exc)
        finally:
            sys.stdout = old
            said = buf.getvalue()
    finally:
        off.S._load_sherpa_diarizer = real_loader
        off.load_cpu_module = real_cpu

    if neg:
        check(loads,
              "BRACO NEGATIVO: o carregador passa a ser chamado MESMO sem folga",
              "%d chamada(s) -- a guarda nao estava a proteger nada" % len(loads))
    else:
        check(rc == off.RC_SEM_FOLGA,
              "main() devolve o rc da recusa", "rc=%d" % rc)
        check(not loads,
              "e os 135 MB de modelos NAO foram carregados",
              "%d chamada(s) ao carregador" % len(loads))
        check("RECUSA" in said,
              "e o dono le no ecra que nao correu", said.strip()[-90:])

        # ---- O PAR: prova que o spy VIOLA ---------------------------------
        loads2 = []

        def spy2(*a, **k):
            loads2.append(1)
            raise AssertionError("CARREGOU OS MODELOS")

        try:
            off.load_cpu_module = lambda: FakeCpu(False, "NENHUM nucleo livre")
            off.S._load_sherpa_diarizer = spy2
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                try:
                    off.main([clip, "--ignore-load"])
                    raised = None
                except AssertionError as exc:
                    raised = str(exc)
            finally:
                sys.stdout = old
        finally:
            off.S._load_sherpa_diarizer = real_loader
            off.load_cpu_module = real_cpu

        check(loads2 and raised,
              "O PAR: com --ignore-load o carregador E' chamado, logo o check "
              "anterior mede alguma coisa",
              "%d chamada(s), exc=%r" % (len(loads2), raised))

    # ---- rc=3 continua a ser 'nenhum clip' --------------------------------
    print("\nOS OUTROS rc's NAO MUDARAM")
    rc_none = off.main([os.path.join(tmp, "nao-existe.wav")])
    check(rc_none == 3,
          "sem clips continua a ser rc=3 (a guarda e' depois)", "rc=%d" % rc_none)

    # ---- A LIGACAO REAL, sem carregar modelos ------------------------------
    # Todos os checks acima encenam `load_cpu_module`. Se esse caminho levar ao
    # ficheiro errado, a guarda continua a passar e o script que a consome fica
    # a ler que "nao ha nucleo livre" para sempre -- ou pior, a aceitar sempre.
    # Este check e' o unico que passa pelo `_cpu-load.py` a serio, e custa ~1,2 s
    # de amostragem: nenhum byte de modelo.
    print("\nA LIGACAO REAL, sem carregar um so modelo")
    real = off.load_cpu_module()
    check(real is not None and hasattr(real, "load_ok"),
          "`load_cpu_module()` encontra mesmo o `_cpu-load.py` (tem hifen no "
          "nome, so se carrega por caminho)", type(real).__name__)
    if real is not None and hasattr(real, "load_ok"):
        rc_real, why_real = off.guard(real, False)
        check(rc_real in (0, off.RC_SEM_FOLGA),
              "e o veredicto e' um dos dois legitimos, nunca um terceiro",
              "rc=%d" % rc_real)
        check(bool(why_real) and why_real != "carga NAO LIDA",
              "com o modulo real a frase da carga NAO e' 'nao lida'",
              why_real)
        rc_live, why_live = real.load_ok()
        check(isinstance(rc_live, bool) and bool(why_live),
              "`load_ok()` real devolve (bool, frase) nesta maquina",
              why_live)

    print("-" * 78)
    if FAILURES:
        print("VERDICT: FAIL  (%d/%d: %s)"
              % (len(FAILURES), CHECKS[0], "; ".join(FAILURES)))
        return 1
    if neg:
        print("VERDICT: PASS  (%d/%d)  -- este era o BRACO NEGATIVO: PASS "
              "significa que a guarda esta a FAZER ALGUMA COISA."
              % (CHECKS[0], CHECKS[0]))
        return 0
    print("VERDICT: PASS  (%d/%d checks)" % (CHECKS[0], CHECKS[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())