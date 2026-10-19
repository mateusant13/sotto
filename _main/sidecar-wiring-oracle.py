"""Portao da LIGACAO do sidecar -- sem lancar a shell, sem abrir um device.

POR QUE ESTE INSTRUMENTO EXISTE, E PORQUE E' ESTATICO
-----------------------------------------------------
A shell e' `app/webview/sotto_webview.py`, 651 781 B, e a sua propria bateria
(`_audit-verify-all.cmd`) lanca a shell dezenas de vezes -- proibido nesta casa.
Por isso este portao NAO lanca nada. Ele:

  * le a shell como texto, substitui o que o braco negativo precisa, e extrai a
    classe `SpeakerSidecar` + `default_speaker_sidecar_path` + `default_python`
    **com o fecho transitivo delas**, compilando-as num namespace com stubs;
  * EXECUTA essa parte de facto: spawn, flags, recusa por ficheiro em falta,
    Popen que rebenta, stop idempotente;
  * AFIRMA sobre o texto as coisas que so a execucao nao mostra (quando o
    sidecar arranca, onde e' parado, se a flag existe).

O BRACO NEGATIVO NAO E' SOBRE O TEXTO. A primeira versao fazia `broken =
src.replace(...)` e depois afirmava que a substituicao tinha村长occurido -- o que
e' trivialmente verdade e prova NADA. Agora o mutante e' **executado**: a classe
extraida da copia quebrada corre no mesmo sandbox, e os arms comportamentais
têm de ir a RED. Uma mutacao que so muda o texto e' decorativa.

O QUE UM BRAÇO JÁ APANHOU NESTE FICHEIRO, E VALE A PENA
--------------------------------------------------------
O arm "a flag chega ao worker por ARGV" foi a RED porque a shell iniciava o
SIDECAR com `--speakers` e nunca o passava ao WORKER -- que e' quem o consome.
Um diarizador de 207 MB a correr e uma bridge sem o flag que le o seu ficheiro
e' o pior dos dois mundos, e so este par -- o texto que diz `--speakers` e o
comportamento do `start` -- o diz.
"""
import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")

rows = []
#: Uma lista de um elemento, e nao uma variavel simples: `arm = "x"` dentro de
#: `main()` criaria uma LOCAL, e `chk` leria a global -- os mutantes ficavam
#: etiquetados com o arm anterior e o `--neg-arm` contava ZERO deles.
ARM = [""]


def chk(cond, name, why=""):
    rows.append((ARM[0], name, bool(cond)))
    print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
    if not cond and why:
        print("         %s" % why)
    return bool(cond)


def func_node(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def seg(src, node):
    return ast.get_source_segment(src, node) or "" if node is not None else ""


class _FakePopen:
    def __init__(self, argv, **kw):
        self.argv = list(argv)
        self.pid = 4242
        self._alive = True
        self.terminated = False
        self.kw = kw

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self.terminated = True
        self._alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self._alive = False


def sandbox(src):
    """Compile the sidecar's OWN code, in isolation, with stubbed modules."""
    tree = ast.parse(src)
    want_f = {"default_python", "default_speaker_sidecar_path"}
    want_c = {"SpeakerSidecar"}
    body = [n for n in tree.body
            if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name in want_f)
            or (isinstance(n, ast.ClassDef) and n.name in want_c)]
    missing = want_f - {n.name for n in body} | want_c - {n.name for n in body}
    if missing:
        raise SystemExit("SETUP: nao encontrei %s na shell" % sorted(missing))
    calls = []
    ns = {
        "os": os,
        "json": __import__("json"),
        "shutil": shutil,
        "sys": sys,
        "__name__": "sandbox",
        "__file__": SHELL,
        "log": lambda m: calls.append(("log", m, None)),
        #: DEVNULL/PIPE/STDOUT foram-me faltando na primeira versao: sem DEVNULL
        #: o spawn levantava AttributeError, a classe apanhava e reportava
        #: SIDECAR_SPAWN_FAILED (como deve ser) e o arm 5 falhava por uma razao
        #: que nao era o que ele media. O stub estava errado, nao a classe.
        "subprocess": types.SimpleNamespace(
            Popen=(lambda argv, **kw: (calls.append(("spawn", list(argv), kw)), _FakePopen(argv, **kw))[1]),
            DEVNULL=-3, PIPE=-1, STDOUT=-2),
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), SHELL, "exec"), ns)
    return ns, calls


def behaviour(ns, calls, prefix):
    """The arms that only a REAL run can answer. Run against any namespace."""
    Sc = ns["SpeakerSidecar"]
    target = os.path.join(HERE, "_sidecar_probe_alvo.py")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("# alvo de teste\n")
    try:
        ARM[0] = prefix + " arranque"
        missing = Sc(sidecar_path=os.path.join(HERE, "_nao-existe.py"))
        chk(missing.start("t") is False, prefix + "6 ficheiro em falta recusa")
        chk(missing.child is None, prefix + "6b e nao deixa filho para tras")

        s = Sc(sidecar_path=target)
        before = len(calls)
        started = s.start("t")
        spawns = [c for c in calls[before:] if c[0] == "spawn"]
        # MEDIDO: `calls[-1]` era a entrada de LOG, nao a de spawn, e `kw`
        # chegava None -- o arm rebentou em vez de falhar. Um arm que rebenta
        # nao diz nada; um arm que falha diz.
        chk(started is True and len(spawns) == 1,
            prefix + "5 arranca com exactamente um spawn",
            "spawns=%d, logs=%s" % (len(spawns),
                                    [c[1] for c in calls[before:] if c[0] == "log"]))
        # MEASURED: era [1], que e' o ARGV. A entrada e' (kind, argv, kwargs),
        # logo as flags vivem no indice 2 -- e um arm que olha para o sitio
        # errado falha pela razao errada.
        kw = spawns[-1][2] if spawns else {}
        flags = kw.get("creationflags", 0) or 0
        chk(bool(flags & 0x08000000),
            prefix + "5a CREATE_NO_WINDOW -- nunca uma janela de consola", hex(flags))
        chk(bool(flags & 0x00004000),
            prefix + "5b BELOW_NORMAL_PRIORITY_CLASS -- leve para o PC do dono",
            hex(flags))
        chk(s.running is True, prefix + "5c reports running")
        chk(s.stop("t") is True, prefix + "8 stop() funciona")
        chk(s.stop("t") is False, prefix + "8b stop() e' idempotente")

        class Boom:
            def __init__(self, *a, **k):
                raise OSError("simulado")

        #: O `subprocess` trocado e' o do SANDBOX. A primeira versao trocou o do
        #: modulo REAL, que o codigo sob teste nunca vai buscar: o arm passou a
        #: falhar sem o ter testado.
        real_sp = ns["subprocess"].Popen
        ns["subprocess"].Popen = Boom
        try:
            bad = Sc(sidecar_path=target)
            chk(bad.start("t") is False, prefix + "7 um Popen que falha nao levanta")
            chk(bad.child is None, prefix + "7b e nao deixa meio filho")
        finally:
            ns["subprocess"].Popen = real_sp
    finally:
        if os.path.exists(target):
            os.remove(target)


def source():
    with open(SHELL, "r", encoding="utf-8") as fh:
        return fh.read()


def wiring(src, prefix):
    """The arms that only reading the source can answer."""
    tree = ast.parse(src)
    ARM[0] = prefix + " ligacao"
    chk("'--speakers'" in src, prefix + "1 a shell declara --speakers")
    sw = seg(src, func_node(tree, "start_worker"))
    chk("extra_args=" in sw and "--speakers" in sw,
        prefix + "2 a flag chega ao WORKER por ARGV",
        "procura --speakers na construcao de WorkerBridge dentro de start_worker")
    chk("SOTTO_SPEAKERS" not in src,
        prefix + "3 nenhuma chave de ambiente nova para esta feature",
        "SOTTO_SPEAKERS apareceria no _child_env e partiria o ARM e")

    ARM[0] = prefix + " contrato de ambiente"
    env_src = seg(src, func_node(tree, "_child_env"))
    expected = {"SOTTO_CAPTURE_MODE", "SOTTO_AUDIO_DEVICE", "SOTTO_TARGET_PID"}
    found = set(re.findall(r"SOTTO_[A-Z_]+", env_src))
    chk(env_src and found == expected,
        prefix + "3b _child_env acrescenta EXACTAMENTE o conjunto que ja tinha",
        "esperado %s, encontrado %s" % (sorted(expected), sorted(found)))

    ARM[0] = prefix + " argv"
    init = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.ClassDef) and n.name == "WorkerBridge"), None)
    init_src = "".join(seg(src, n) for n in (init.body if init else [])
                       if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    chk("extra_args=None" in init_src,
        prefix + "4 WorkerBridge aceita extra_args com omissao vazia")
    spawn_src = seg(src, func_node(tree, "_spawn"))
    chk("argv = [self.command, self.worker_path] + list(self.extra_args)"
        in spawn_src,
        prefix + "4b e argv = [command, path] + extra_args")

    ARM[0] = prefix + " quando"
    i_start = sw.find("self.bridge.start(reason)")
    i_side = sw.find("sidecar.start(reason)")
    chk(i_start >= 0 and i_side > i_start,
        prefix + "9 o sidecar arranca DEPOIS de o worker ter arrancado")
    chk(re.search(r"if started:\s*\n(?:.*\n)*?\s*if getattr\(self\.args, 'speakers'",
                  sw) is not None,
        prefix + "9b e so quando os.args.speakers esta ligado")
    chk("sidecar.start" not in sw[:i_start],
        prefix + "9c nada arranca o sidecar ANTES do worker -- um worker recusado "
                 "nao deixa um diarizador a correr contra ninguem")
    chk(re.search(r"stop_hot_reload\('closing'\).*?stop\('shell-closing'\)",
                  src, re.S) is not None,
        prefix + "10 o sidecar e' parado no fecho da shell")
    chk("stop('shell-exit')" in src, prefix + "10b e na saida")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    src = source()
    ns, calls = sandbox(src)
    wiring(src, "")
    ARM[0] = "caminho"
    path = ns["default_speaker_sidecar_path"]()
    chk(os.path.isfile(path), "11 default_speaker_sidecar_path() existe", path)
    behaviour(ns, calls, "")

    if args.neg_arm:
        # O MUTANTE E' EXECUTADO. A versao anterior confirmava que a substituicao
        # de texto tinha acontecido -- trivialmente verdade, e prova nada.
        broken = src.replace(
            "flags |= 0x00004000          # BELOW_NORMAL_PRIORITY_CLASS",
            "pass  # mutante: sem prioridade reduzida")
        if broken == src:
            print("SETUP: a ancora do mutante nao existe mais na shell")
            return 2
        ns2, calls2 = sandbox(broken)
        before = len(rows)
        behaviour(ns2, calls2, "mutante ")
        mutant_rows = rows[before:]
        # MEASURED: a polaridade estava INVERTIDA. O que um braco negativo
        # quer e' que o mutante CAIA; a versao anterior guardava os mutantes
        # cujo arm 5b tinha PASSADO e chamava-lhe "sobrevivente", ou seja
        # tratava o mutante que se annunciou como "caiu, como deve" numa
        # VERDICT: FAIL. O mutante estava a cair bem; o portao é que o
        # condemned por working.
        fell = [r for r in mutant_rows if r[1].endswith(
            "5b BELOW_NORMAL_PRIORITY_CLASS -- leve para o PC do dono")
            and not r[2]]
        ok = bool(fell)
        print("\n  o mutante (sem BELOW_NORMAL) %s"
              % ("CAIU -- a porta mede o que diz" if ok
                 else "NAO CAIU -- a porta nao mede o que diz"))
        rows[:] = [r for r in rows if r[0] != "mutante "] + [
            ("mutante", "o mutante sem BELOW_NORMAL vai a RED", ok)]
        if not ok:
            print("VERDICT: FAIL")
            return 1
        print("VERDICT: PASS")
        return 0

    failed = [r for r in rows if not r[2]]
    print("\narms %d/%d" % (len(rows) - len(failed), len(rows)))
    print("VERDICT: %s" % ("PASS" if not failed else "FAIL"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())