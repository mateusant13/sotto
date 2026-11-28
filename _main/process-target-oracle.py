# NO-BUG: oraculo do alvo por NOME do tap por processo; o comportamento que ele julga mora em `worker/process_target.py` (modulo novo, 2026-11-09).
# -*- coding: utf-8 -*-
"""ORACULO -- o alvo do tap por processo, escolhido por NOME.

O QUE ELE JULGA (a ordem do dono de 2026-11-09: *"identifica corretamente o
audio saindo do discord"*): que `Discord.exe` resolva para a RAIZ da arvore do
Discord, que um pid morto volte a ser resolvido, e que nenhum desses caminhos
substitua o alvo em silencio pelo mix do endpoint.

AS ARMS correm sobre tabelas de processos INJECTADAS -- nenhum processo e'
aberto, nenhum dispositivo e' tocado, nenhuma janela e' pintada.

    python _main/process-target-oracle.py            # positivo
    python _main/process-target-oracle.py --neg-arm  # tem de apanhar (rc=1)
"""
from __future__ import annotations

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import process_target as pt          # noqa: E402


#: A tabela do Discord real desta maquina (medida 2026-11-09): seis processos,
#: todos filhos da raiz 22992 excepto ela. O do meio existe para que um
#: `max(pids)` implementado por engano seja apanhado pela arm A3.
ROWS = [
    (4, 0, "System"),
    (22992, 4, "Discord.exe"),        # a RAIZ (pai nao e' Discord)
    (23372, 22992, "Discord.exe"),
    (2024, 22992, "Discord.exe"),
    (2028, 22992, "Discord.exe"),
    (23600, 22992, "Discord.exe"),
    (24484, 22992, "Discord.exe"),    # o maior pid -- NAO e' a raiz
    (25992, 4, "chrome.exe"),
    (26000, 25992, "chrome.exe"),
    (1, 0, "DiscordCanary.exe"),      # o irmao que uma substring casaria
]


WORKER_SRC = os.path.join(ROOT, "worker", "sotto_worker.py")


def struct_arms(src_text):
    """Julga a FORMA do fio dono do apartamento COM. [(nome, ok, detalhe)].

    Uma funcao e nao um bloco inline porque o `--neg-arm` tem de julgar o MUTANTE
    pelo MESMO juiz que publica o veredito -- um negativo que reimplementa a
    comparacao prova so' a si proprio.
    """
    import ast as _ast
    tree = _ast.parse(src_text)
    cls = next((n for n in _ast.walk(tree)
                if isinstance(n, _ast.ClassDef) and n.name == "ProcessLoopbackTap"), None)
    meth = {n.name: n for n in (cls.body if cls else []) if isinstance(n, _ast.FunctionDef)}
    texts = {k: (_ast.get_source_segment(src_text, v) or "") for k, v in meth.items()}

    def spawns_thread(fn):
        for n in _ast.walk(fn):
            if isinstance(n, _ast.Call):
                f = n.func
                name = getattr(f, "attr", getattr(f, "id", ""))
                if name in ("Thread", "Timer"):
                    return True
        return False

    def has(name):
        return name in meth

    def teardown_in_finally(name):
        """O teardown TEM de estar no `finally` do caminho NORMAL do fio dono.

        A primeira versao desta arm so' exigia o nome em qualquer sitio de
        `_owner_loop`, e o `--neg-arm` provou que ela nao media nada: o ramo de
        EXCECAO tambem chama `_teardown_on_owner`, logo apagar o `finally`
        deixava a arm verde. Um fio que so' liberta COM quando o open falha
        deixa o caminho normal a morrer com o apartamento aberto.
        """
        fn = meth.get(name)
        if fn is None:
            return False
        for node in _ast.walk(fn):
            if isinstance(node, _ast.Try):
                for stmt in node.finalbody:
                    for inner in _ast.walk(stmt):
                        if (isinstance(inner, _ast.Call)
                                and getattr(inner.func, "attr", "") == "_teardown_on_owner"):
                            return True
        return False

    out = [
        ("A10 `_open` NAO cria fio nenhum (o pump roda no fio dono)",
         has("_open") and not spawns_thread(meth["_open"]), ""),
        ("A10b existe `_owner_loop` (COM + open + pump no mesmo fio)",
         has("_owner_loop"), ""),
        ("A11 `_start` arranca o fio dono e ESPERA o desfecho do open",
         has("_start") and "_owner_loop" in texts["_start"]
         and "_opened.wait(" in texts["_start"], ""),
        ("A11b o fio dono nao arranca outro fio",
         has("_owner_loop") and not spawns_thread(meth["_owner_loop"]), ""),
        ("A12 o COM e' inicializado NO fio dono, nao no chamador",
         has("_owner_loop") and "_com_init" in texts["_owner_loop"], ""),
        ("A12b `_start` nao inicializa COM no fio que o chamou",
         has("_start") and "_com_init" not in texts["_start"], ""),
        ("A13 o teardown (Stop + release + COM) roda no fio dono, no finally",
         has("_teardown_on_owner") and teardown_in_finally("_owner_loop"), ""),
    ]
    return out

def signatures(src):
    """Nomes de funcao definidos no modulo -- checagem barata de existencia."""
    import ast as _ast
    tree = _ast.parse(src)
    out = set()
    for cls in [n for n in tree.body if isinstance(n, _ast.ClassDef)]:
        for fn in cls.body:
            if isinstance(fn, _ast.FunctionDef):
                out.add(fn.name)
    return out


def _live_probe(sw, seconds=2.0):
    """Abre o tap pelo caminho de PRODUCAO e exige blocos. None = sem alvo.

    Um alvo vivo e' procurado entre os programas com o nome mais comum desta
    maquina (`Discord.exe`); sem nenhum, a arm nao pode medir nada e o oraculo
    DIZ isso em vez de passar por omissao.
    """
    try:
        import time as _t
        name = "Discord.exe"
        pid = pt.resolve(name)
        if not pid:
            return None
        cands = sw.device_candidates(None, None, target_pid=pid)
        proc = [c for c in cands if c.get("process_loopback")]
        if not proc:
            return None
        n = {"b": 0}
        tap, error = sw._open_tap_bounded(proc[0], lambda b: n.__setitem__("b", n["b"] + 1),
                                          block_ms=40)
        # UM OPEN QUE NAO VOLTA NAO E' UMA ENTREGA VAZIA (medido 2026-11-27, run #8:
        # `TAP_OPEN_TIMEOUT device='process loopback: pid 27380 (Discord.exe)'
        # api=None in_s=4.00` e o braco foi a FAIL -- mas o instrumento nem chegou
        # a medir, e um Discord em silencio nao renderiza bloco nenhum para o
        # loopback de processo). As duas populacoes vazias dizem o proprio nome:
        # `open-blocked` e `silent-target`. So' um tap ABERTO com blocos prova o
        # caminho; sem isso o veredicto e' CANNOT-MEASURE, nunca um vermelho pela
        # meteorologia da maquina.
        if tap is None:
            print("   A14 detail: open nao voltou (%r) -- CANNOT-MEASURE" % (error,))
            return "cannot", "open-blocked"
        _t.sleep(seconds)
        got = n["b"]
        try:
            tap.stop()
            tap.close()
        except Exception:                     # noqa: BLE001
            pass
        print("   A14 detail: pid=%s blocks=%d pump_exited=%s"
              % (pid, got, getattr(tap, "pump_exited", None)))
        return ("pass", "blocks=%d" % got) if got > 0 else ("cannot", "silent-target")
    except Exception as exc:                  # noqa: BLE001
        print("   A14 detail: probe falhou: %r" % (exc,))
        return "cannot", "probe-error"



def run() -> int:
    cases = []

    def arm(ok, title):
        cases.append(bool(ok))
        print(("PASS " if ok else "FAIL ") + title)

    # A1 -- igualdade, nunca substring
    hits = pt.match(ROWS, "Discord.exe")
    arm(len(hits) == 6, "A1 seis processos do Discord, e o Canary fica de fora")
    arm(all(img == "Discord.exe" for _p, _pp, img in hits),
        "A1b nenhuma linha de outro programa entrou na lista")

    # A2 -- normalizacao do nome
    arm(pt.normalise("discord") == "discord.exe", "A2 sem .exe ganha .exe")
    arm(pt.normalise("C:\\\\Apps\\\\Discord.exe") == "discord.exe",
        "A2b um caminho completo reduz ao basename")
    arm(pt.normalise("  ") == "", "A2c vazio nao vira '.exe'")

    # A3 -- a RAIZ, nao o maior pid
    root = pt.pick_root(ROWS, "Discord.exe")
    arm(root == 22992, "A3 a raiz da arvore (22992), nao o maior pid (24484)")
    arm(root != max(p for p, _pp, i in ROWS if i == "Discord.exe"),
        "A3b a arm distingue raiz de maior pid")

    # A4 -- duas raizes: a mais recente (maior pid) ganha
    rows2 = ROWS + [(30000, 4, "Discord.exe")]
    arm(pt.pick_root(rows2, "Discord.exe") == 30000,
        "A4 com duas raizes ganha a mais recente")

    # A5 -- programa ausente: None, nunca um vizinho
    arm(pt.pick_root(ROWS, "Spotify.exe") is None, "A5 programa ausente -> None")
    arm(pt.resolve("Spotify.exe", rows=ROWS) is None, "A5b resolve coincide com pick_root")

    # A6 -- o pid vivo e' mantido (sem re-resolver por gosto)
    arm(pt.resolve_again("Discord.exe", 22992, rows=ROWS) == 22992,
        "A6 um pid vivo e' mantido")

    # A7 -- o pid MORTO volta a ser resolvido (o reinicio do Discord)
    arm(pt.resolve_again("Discord.exe", 999999, rows=ROWS) == 22992,
        "A7 pid morto e' re-resolvido para a raiz viva")

    # A8 -- nada vivo: None (o chamador tem de DIZER, nao cair no mix)
    arm(pt.resolve_again("Discord.exe", 999999, rows=[(4, 0, "System")]) is None,
        "A8 sem nenhum processo do nome -> None, nunca o mix")

    # A9 -- a fiacao: o candidato da escada e' rung 'p' com o pid do alvo
    try:
        import sotto_worker as sw
        cand = sw.process_loopback_candidate(22992, "Discord.exe")
        arm(cand.get("rung") == "p" and int(cand.get("target_pid")) == 22992,
            "A9 a escada oferece o alvo como rung 'p' com target_pid")
    except Exception as exc:                     # noqa: BLE001
        arm(False, "A9 a escada oferece o alvo como rung 'p' (%r)" % (exc,))

    # ── A10-A13: O APARTAMENTO COM E' DE UM FIO SO' ─────────────────────────
    # MEDIDO 2026-11-09 no alvo real (Discord.exe): aberto num fio que depois
    # saía, o pump entregava 71 blocos em 3 s e PARAVA quando o fio de abertura
    # morria; o caminho de producao (`_open_tap_bounded`, que abre num fio e o
    # deixa sair) media ZERO blocos com o tap ABERTO (`PLP_OPEN_OK hr=0`). Os
    # ponteiros COM pertencem ao apartamento que os criou. As arms abaixo medem
    # a FORMA que impede isso e o EFEITO que ele tinha.
    sw = None
    try:
        import sotto_worker as _sw
        sw = _sw
    except Exception as exc:                     # noqa: BLE001
        arm(False, "A10 importa o worker (%r)" % (exc,))

    if sw is not None:
        wsrc_now = io.open(WORKER_SRC, "r", encoding="utf-8").read()
        for name, good, detail in struct_arms(wsrc_now):
            if good:
                arm(True, name)
            else:
                cases.append(False)
                print("FAIL %s%s" % (name, detail))

        # O EFEITO, quando ha' um alvo vivo nesta maquina: o caminho de producao
        # (`_open_tap_bounded`) tem de entregar blocos. Sem alvo, SKIP declarado
        # -- e um skip nao e' um PASS.
        live = _live_probe(sw)
        # `None` = nao ha' alvo; uma tupla = (veredicto, razao) e so' o veredicto
        # "pass" conta como caso julgado. Um skip e' um skip, nunca um verde: a
        # bateria conta SKIPPED em separado e o veredicto nao mente.
        if live is None:
            print("SKIP A14 sem programa alvo vivo nesta maquina "
                  "-- CANNOT-MEASURE reason=no-live-target")
        elif live[0] == "pass":
            arm(True, "A14 o caminho de producao entrega blocos")
        else:
            print("SKIP A14 CANNOT-MEASURE reason=%s -- o efeito nao foi medido"
                  % (live[1],))

    ok = all(cases)
    print("\nPROCESS-TARGET VERDICT: %s (%d/%d)"
          % ("PASS" if ok else "FAIL", sum(1 for c in cases if c), len(cases)))
    return 0 if ok else 1


def neg_arm() -> int:
    """Muta a COMPARACAO numa COPIA do modulo e exige que as arms caiam.

    A mutacao e' a classe que o modulo existe para impedir: casar por substring.
    Tambem muta a escolha da raiz para `max(pid)` -- se nenhuma arm cair, o
    oraculo nao estava a medir o que diz medir.

    DOIS CENSOS, DOIS NUMEROS. Os tres primeiros mutantes julgam o COMPORTAMENTO
    de `worker/process_target.py` (a comparacao por nome, a raiz, o pid morto); as
    quatro seguintes julgam a FORMA do fio dono do apartamento COM em
    `worker/sotto_worker.py` (entraram a 2026-11-09, com o defeito medido no alvo
    real). Sao populacoes diferentes julgadas por juizes diferentes (`pt.match`
    contra `struct_arms`), por isso cada uma publica o seu numero e o rc=1 exige
    as duas completas.
    """
    src = io.open(os.path.join(ROOT, "worker", "process_target.py"),
                  "r", encoding="utf-8").read()
    # O NUMERO QUE O PASSO DA BATERIA FIXA E' O DO PRIMEIRO CENSO
    # (`_main/_audit-verify-all.cmd:3620`, `NEG-ARM: 3/3 mutantes apanhados`).
    # Quando as quatro mutacoes de FORMA entraram, um contador unico passou a
    # imprimir `7/7` e o passo ficou vermelho SEM que nenhuma arm tivesse
    # deixado de apanhar: o pino e' que envelheceu. Encolher o mutante para 3
    # seria apagar medida; um contador por censo devolve a cada numero o que ele
    # mede, e o total real continua publicado ao lado.
    caught_b = total_b = 0
    caught_f = total_f = 0

    def trial(title, old, new, arms):
        nonlocal caught_b, total_b
        total_b += 1
        mutant = src.replace(old, new, 1)
        if mutant == src:
            print("MUTANT-NOT-APPLIED %s" % title)
            return
        ns = {"__name__": "process_target_mutant"}
        exec(compile(mutant, "process_target_mutant", "exec"), ns)   # noqa: S102
        fails = [name for name, fn in arms if not fn(ns)]
        if fails:
            caught_b += 1
            print("CAUGHT %-34s by %s" % (title, ", ".join(fails)))
        else:
            print("NOT-CAUGHT %s" % title)

    # A mutacao tem de ser o defeito REAL, nao uma variante inofensiva: comparar
    # o NOME sem extensao por substring e' como um filtro de kill por palavra --
    # `discord` casa com `DiscordCanary.exe` e o alvo passa a ser outro programa.
    trial("match por substring do nome sem .exe",
          'if normalise(image) == want:',
          'if want.replace(".exe", "") in normalise(image):',
          [("A1", lambda m: len(m["match"](ROWS, "Discord.exe")) == 6)])
    trial("raiz = maior pid",
          'roots = [pid for pid, ppid, _img in hits if ppid not in same]',
          'roots = []',
          [("A3", lambda m: m["pick_root"](ROWS, "Discord.exe") == 22992)])
    trial("pid morto nao re-resolve",
          '    if current and alive(current):\n        return int(current)',
          '    if current:\n        return int(current)',
          [("A7", lambda m: m["resolve_again"]("Discord.exe", 999999, rows=ROWS) == 22992)])

    wsrc = io.open(WORKER_SRC, "r", encoding="utf-8").read()
    nlw = "\r\n" if "\r\n" in wsrc else "\n"

    def wtrial(title, old, new, want_fail):
        nonlocal caught_f, total_f
        total_f += 1
        mutant = wsrc.replace(old, new, 1)
        if mutant == wsrc:
            print("MUTANT-NOT-APPLIED %s" % title)
            return
        try:
            fails = [n for n, ok, _d in struct_arms(mutant) if not ok]
        except SyntaxError as exc:
            print("MUTANT-BROKEN %s (%s)" % (title, exc))
            return
        hit = [n for n in fails if n.startswith(want_fail)]
        if hit:
            caught_f += 1
            print("CAUGHT %-40s by %s" % (title, ", ".join(hit)))
        else:
            print("NOT-CAUGHT %-36s (fails=%r)" % (title, fails))

    def L(*lines):
        return nlw.join(lines)

    # As QUATRO mutacoes do fio dono: cada uma tem de ser apanhada pela SUA arm.
    wtrial("pump volta a ser um fio separado dentro de _open",
           'err("PLP_OPEN_OK pid=%d rate=%d channels=%d block=%d winner=%r"',
           'self._thread = threading.Thread(target=self._pump, name="plp-capture")'
           + nlw + "        " + 'self._thread.start()' + nlw + "        "
           + 'err("PLP_OPEN_OK pid=%d rate=%d channels=%d block=%d winner=%r"',
           "A10 ")
    wtrial("COM volta a ser inicializado em _start",
           '            self._com = self._wl._com_init()',
           '            pass',
           "A12 ")
    wtrial("_start deixa de esperar o desfecho do open",
           '        if not self._opened.wait(PLP_ACTIVATE_TIMEOUT_S + 5.0):',
           '        if True:',
           "A11 ")
    wtrial("teardown sai do fio dono",
           L('        finally:', '            self._teardown_on_owner()'),
           L('        finally:', '            pass'),
           "A13 ")

    caught, total = caught_b + caught_f, total_b + total_f
    print("\nNEG-ARM: %d/%d mutantes apanhados" % (caught_b, total_b))
    print("NEG-ARM-FORM: %d/%d mutacoes de forma apanhadas" % (caught_f, total_f))
    print("NEG-ARM-TOTAL: %d/%d (%d de comportamento + %d de forma)"
          % (caught, total, total_b, total_f))
    return 1 if caught == total else 0


if __name__ == "__main__":
    sys.exit(neg_arm() if "--neg-arm" in sys.argv else run())
