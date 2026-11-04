"""ORACLE do `_main/hidden-launch.py` -- o unico caminho desta arvore que larga
um filho, e o que a bateria inteira atravessa.

NASCEU DE UM DEFEITO MEDIDO (2026-11-04). `run()` e `popen()` montavam o dict
`kw` com `creationflags` e depois passavam `creationflags=` OUTRA VEZ ao
`subprocess.Popen`:

    TypeError: subprocess.Popen() got multiple values for keyword argument 'creationflags'

O erro acontece ANTES de o filho existir, por isso o efeito medido nao foi um
aviso: `python -c "... m.run(['cmd','/c',r'_main\\_audit-verify-all.cmd']) ..."`
devolveu o Traceback e **nenhum passo da bateria correu**. O `cmd` que aparecia
na saida era o do erro.

PORQUE NENHUM PORTAO APANHOU ISTO. O portao que a AGENTS.md nomeia
(`_main/console-window-gate.py`) nao existe nesta arvore, e mesmo que existisse
ele confere a PRESENCA da bandeira no texto -- e ela estava presente, duas
vezes. Este oraculo confere o EFEITO no sistema operativo.

O QUE ELE MEDE (o filho diz o que o Windows lhe deu):

  A  `hidden-launch.run(['cmd','/c',...])`  -> `GetConsoleWindow() == 0`
  B  `hidden-launch.popen([...])`           -> `GetConsoleWindow() == 0`
  C  CENSO: durante um filho de 3 s, `EnumWindows` nao ve' NENHUMA janela
     visivel de classe de consola pertencente a arvore do filho. Medido, nao
     inferido.
     LIMITE DO INSTRUMENTO, medido nesta corrida: `GetConsoleWindow()` devolve 0
     tambem para um filho lancado SEM a bandeira quando o PAI nao tem consola
     (este harness nao tem), por isso a alca nao serve de controle aqui -- e um
     arm que nao consegue ficar vermelho nao e' uma afirmacao. Fica o censo.
  D  DURACAO: um filho de 3 s devolve depois de >= 3 s, com a saida inteira.
     Um `run` que devolve `rc` sem esperar nao serve para a bateria.

O BRACO NEGATIVO (`--neg-arm`) repoe o DEFEITO numa COPIA do modulo (passar
`creationflags=` outra vez ao `Popen`) e exige A e B VERMELHOS com o
`TypeError`. Sem isso o oraculo ficaria verde com o bug de volta.

Exit codes: 0 PASS, 1 FAIL, 2 setup. Nenhuma janela: os quatro filhos sao
invisiveis por construcao (o controle usa SW_HIDE).
"""
# NO-BUG: instrumento do `hidden-launch` -- mede o EFEITO no sistema operativo
# (GetConsoleWindow do filho) e o braco negativo tira a bandeira numa copia.

from __future__ import annotations

import ctypes
import ctypes.wintypes
from ctypes import wintypes
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
LAUNCHER = os.path.join(HERE, "hidden-launch.py")

CONSOLE_CLASSES = ("ConsoleWindowClass", "PseudoConsoleWindow")


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("cntUsage", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("cntThreads", ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]

CHILD = (
    "import ctypes as c;"
    "h=c.WinDLL('kernel32').GetConsoleWindow();"
    "v=bool(c.WinDLL('user32').IsWindowVisible(c.c_void_p(h))) if h else False;"
    "print('CONSOLE hwnd=%s visible=%s' % (h, v))"
)

RESULTS: list[bool] = []


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arm(name, ok, evidence):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] arm: {name}\n       {evidence}")


def console_of(out: str):
    """`CONSOLE hwnd=<n> visible=<bool>` -> (hwnd, visible) or (None, None)."""
    for line in (out or "").splitlines():
        if line.startswith("CONSOLE "):
            parts = dict(p.split("=", 1) for p in line.split()[1:])
            return int(parts["hwnd"]), parts["visible"] == "True"
    return None, None


def main(argv) -> int:
    neg = "--neg-arm" in argv
    path = LAUNCHER
    tmpdir = None
    if neg:
        src = io.open(LAUNCHER, encoding="utf-8", newline="").read()
        mutant = src.replace(
            "        proc = subprocess.Popen(argv, **kw)",
            "        proc = subprocess.Popen(argv, **kw,"
            " creationflags=CREATE_NO_WINDOW)", 1).replace(
            "    return subprocess.Popen(argv, **kwargs)",
            "    return subprocess.Popen(argv, **kwargs,"
            " creationflags=CREATE_NO_WINDOW)", 1)
        if mutant.count("creationflags=CREATE_NO_WINDOW)") < 2:
            print("NEG-ARM IMPOSSIVEL: as ancoras do `Popen` nao estao no modulo")
            return 2
        tmpdir = tempfile.mkdtemp(prefix="hidden-launch-neg-")
        path = os.path.join(tmpdir, "hidden_launch_mutant.py")
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(mutant)

    try:
        mod = load(path, "hidden_launch_under_test")

        # ── A: `run` ──────────────────────────────────────────────────────
        try:
            rc, out, err = mod.run([sys.executable, "-c", CHILD],
                                   capture=True, timeout=60)
        except Exception as exc:                       # noqa: BLE001
            rc, out, err = None, "", f"{type(exc).__name__}: {exc}"
        hwnd, visible = console_of(out)
        arm("run(): o filho NAO tem console (GetConsoleWindow()==0)",
            rc == 0 and hwnd == 0 and visible is False,
            f"rc={rc} hwnd={hwnd} visible={visible} err={err.strip()[:80]!r}")

        # ── B: `popen` ────────────────────────────────────────────────────
        try:
            proc = mod.popen([sys.executable, "-c", CHILD],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
            pout, perr = proc.communicate(timeout=60)
            prc = proc.returncode
        except Exception as exc:                       # noqa: BLE001
            pout, perr, prc = "", f"{type(exc).__name__}: {exc}", None
        hwnd2, visible2 = console_of(pout)
        arm("popen(): o filho NAO tem console (GetConsoleWindow()==0)",
            prc == 0 and hwnd2 == 0 and visible2 is False,
            f"rc={prc} hwnd={hwnd2} visible={visible2} "
            f"err={perr.strip()[:80]!r}")

        # ── C: CENSO de janelas visiveis do FILHO durante 3 s ────────────
        # O censo filtra pela ARVORE do filho: a maquina tem janelas
        # `PseudoConsoleWindow` visiveis que sao do terminal do harness, nao
        # deste filho -- contar todas transformaria o arm num alarme falso.
        import threading
        seen = []
        samples = [0]

        def census(roots, stop_at):
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            def descendants(pid):
                out = {pid}
                snap = kernel32.CreateToolhelp32Snapshot(2, 0)
                entry = PROCESSENTRY32W()
                entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
                if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
                    rows = []
                    while True:
                        rows.append((int(entry.th32ProcessID),
                                     int(entry.th32ParentProcessID)))
                        if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                            break
                else:
                    rows = []
                kernel32.CloseHandle(snap)
                grew = True
                while grew:
                    grew = False
                    for pid_, parent in rows:
                        if parent in out and pid_ not in out:
                            out.add(pid_)
                            grew = True
                return out

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def cb(hwnd, _l):
                if not user32.IsWindowVisible(hwnd):
                    return True
                owner = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
                if int(owner.value) not in tree_now[0]:
                    return True
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 256)
                if cls.value in CONSOLE_CLASSES:
                    seen.append((int(owner.value), cls.value))
                return True

            tree_now = [set(roots)]
            while time.time() < stop_at:
                tree_now[0] = set()
                for root in roots:
                    tree_now[0] |= descendants(root)
                user32.EnumWindows(cb, 0)
                samples[0] += 1
                time.sleep(0.2)

        stop_at = time.time() + 3.4
        try:
            proc = mod.popen(
                [sys.executable, "-c", "import time;time.sleep(3.0);print('OK')"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            t = threading.Thread(target=census, args=([proc.pid], stop_at),
                                 daemon=True)
            t.start()
            pout5, perr5 = proc.communicate(timeout=120)
            t.join(timeout=2.0)
            rc5, err5 = proc.returncode, perr5
        except Exception as exc:                       # noqa: BLE001
            rc5, pout5, err5 = None, "", f"{type(exc).__name__}: {exc}"
        # `samples > 0` e' o que impede um verde VAZIO: um censo que nao correu
        # tambem devolve `seen == []`, e essa era a forma de este arm mentir.
        arm("CENSO: nenhuma janela de consola visivel na arvore do filho",
            rc5 == 0 and samples[0] > 0 and not seen,
            f"rc={rc5} amostras={samples[0]} janelas={seen[:4]!r} "
            f"err={err5.strip()[:60]!r}")

        # ── D: DURACAO ────────────────────────────────────────────────────
        t0 = time.time()
        try:
            rc4, out4, _ = mod.run(
                [sys.executable, "-c", "import time;time.sleep(3.0);print('DONE')"],
                capture=True, timeout=120)
        except Exception as exc:                       # noqa: BLE001
            rc4, out4 = None, f"{type(exc).__name__}: {exc}"
        wall = time.time() - t0
        arm("run() ESPERA pelo filho: 3 s de filho => >=3 s de espera e a saida",
            rc4 == 0 and wall >= 3.0 and "DONE" in out4,
            f"rc={rc4} wall={wall:.2f}s out={out4.strip()!r}")

        failed = RESULTS.count(False)
        if neg:
            # A CONVENCAO DA CASA: o negativo devolve 1 quando APANHA os mutantes.
            caught = failed > 0
            print("NEG-ARM PASS: %d arm(s) vermelha(s) com o TypeError de volta"
                  % (failed) if caught else
                  "NEG-ARM FAIL: o mutante do TypeError NAO derrubou nenhuma arm")
            return 1 if caught else 0
        print(f"hidden-launch-oracle: {len(RESULTS) - failed} PASS / {failed} FAIL "
              f"({len(RESULTS)} arms)  impl={path}")
        return 0 if failed == 0 else 1
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
