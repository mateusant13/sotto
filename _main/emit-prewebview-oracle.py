# NO-BUG: ORACLE do feed `emit_async` SEM PAGINA -- o defeito que enchia o log.
"""ORACLE do feed `emit_async` SEM PAGINA -- o defeito que enchia o log.

O QUE FOI MEDIDO (2026-11-04, instancia propria pid 42340, escondida):
`CAPTION_IN` a chegar (a fonte do YouTube a funcionar) e, por cada amostra do
medidor, um `WARN POSTED_CALLABLE_FAILED fn=_run AttributeError: 'NoneType'
object has no attribute 'ExecuteScriptAsync'` -- **541 linhas em ~60 s**
(`grep -c`), sempre com `core=None` porque o WebView2 nunca inicializou nessa
instancia (`WEBVIEW2_INIT_FAILED 0x80010108 RPC_E_DISCONNECTED`, 02:48:24).

O DEFEITO NAO E' "o core esta' a None": `emit` e `exec_js_post` ja' declaram que
o pipeline de legendas arranca ANTES do WebView2, de proposito. O defeito e' o
feed de `stats` nao ter a mesma guarda -- ele punha a `AttributeError` DENTRO do
`Invoke`, o WinForms devolvia-a a' thread que postou, e o `guarded()` do `_post`
a transformava numa linha por amostra.

AS ARMS (nenhuma larga processo, nenhuma abre janela):

  A  com `core=None` e 50 pushes: NENHUMA excepcao, e **UMA** linha
     `EMIT_ASYNC_PREWEBVIEW` -- nao 50.
  B  com `core` vivo: o script E' postado e carrega o payload MAIS NOVO (o
     latch nao pode ter sido quebrado pela guarda: um feed que para de chegar e'
     outro defeito).
  C  a guarda nao engole o canal normal depois de a pagina existir: com
     `core=None` primeiro e `core` vivo depois, o mesmo `kind` volta a postar.

O BRACO NEGATIVO (`--neg-arm`) tira a guarda de uma COPIA do shell e exige a
arm A VERMELHA com `AttributeError` -- exactamente o que o log do dono mostrava.
rc=1 quer dizer APANHOU o mutante.

    python _main/emit-prewebview-oracle.py
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import types

SHELL = r"H:\sotto\app\webview\sotto_webview.py"
GUARD = "if self.core is None or self.webview2 is None:"


def _stub_system() -> None:
    """`emit_async` faz `from System import ...` no corpo: sem pythonnet neste
    processo, o stub entra em `sys.modules` ANTES do import do shell."""
    class _Sub:
        def __init__(self, *args, **kwargs):
            # `Func[Object](meu_lambda)` no pythonnet devolve o delegate que
            # CORRE o lambda: o stub guarda-o para o `Invoke` o chamar.
            self._target = args[0] if args and callable(args[0]) else None

        def __class_getitem__(cls, item):
            return cls

    sysmod = types.ModuleType("System")
    for name in ("Action", "Func", "Object", "String"):
        setattr(sysmod, name, _Sub)
    tasks = types.ModuleType("System.Threading.Tasks")
    tasks.Task = _Sub
    sysmod.Threading = types.ModuleType("System.Threading")
    sysmod.Threading.Tasks = tasks
    sys.modules["System"] = sysmod
    sys.modules["System.Threading"] = sysmod.Threading
    sys.modules["System.Threading.Tasks"] = tasks


class _Task:
    IsFaulted = False
    Exception = None

    def ContinueWith(self, _action):
        return self


class _Core:
    def __init__(self):
        self.scripts = []

    def ExecuteScriptAsync(self, script):
        self.scripts.append(script)
        return _Task()


class _WebView2:
    def Invoke(self, fn):
        target = getattr(fn, '_target', None) or fn
        target()


class _Shell:
    """O suficiente do shell para `emit_async` correr o codigo REAL."""

    def __init__(self, core, webview2):
        import threading
        self.core = core
        self.webview2 = webview2
        self._emit_lock = threading.Lock()
        self._emit_pending = {}
        self.logs = []

    def _post(self, fn):
        # `_post` e' `BeginInvoke`: aqui corre o callable, que e' o que acontece
        # quando a UI thread o apanha -- e era o `guarded()` dele que escrevia
        # o WARN no log vivo.
        fn()
        return True


def _load(path):
    # o mutante vive num tmpdir e importa os irmaos do shell (`hot_reload`,
    # `panel_state`): o diretorio REAL fica no caminho nos dois casos.
    sys.path.insert(0, os.path.dirname(SHELL))
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("sotto_shell_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv) -> int:
    neg = "--neg-arm" in argv
    _stub_system()

    path = SHELL
    tmpdir = ""
    if neg:
        src = io.open(SHELL, encoding="utf-8", newline="").read()
        if GUARD not in src:
            print("NEG-ARM IMPOSSIVEL: a guarda nao esta' no shell")
            return 2
        # o mutante MANTEM a estrutura e desliga a CONDICAO: trocar a linha por
        # `pass` deixava o corpo do `if` sem pai (IndentationError, medido).
        stripped = src.replace(
            "if self.core is None or self.webview2 is None:\r\n",
            "if False and (self.core is None or self.webview2 is None):\r\n", 1)
        tmpdir = tempfile.mkdtemp(prefix="emit-prewebview-neg-")
        path = os.path.join(tmpdir, "sotto_webview_mutant.py")
        io.open(path, "w", encoding="utf-8", newline="").write(stripped)

    try:
        mod = _load(path)
        captured = []
        mod.log = lambda msg: captured.append(str(msg))
        mod.warn = lambda msg: captured.append('WARN ' + str(msg))
        results = []

        def arm(name, ok, detail):
            results.append(bool(ok))
            print("[%s] arm: %s\n       %s"
                  % ("PASS" if ok else "FAIL", name, detail))

        # arm A -- 50 pushes sem pagina, UMA linha, nenhuma excepcao
        shell = _Shell(None, None)
        raised = ""
        for i in range(50):
            try:
                mod.SottoShell.emit_async(shell, "stats", {"n": i})
            except Exception as exc:                     # noqa: BLE001
                raised = "%s: %s" % (type(exc).__name__, exc)
                break
        lines = [m for m in captured if "EMIT_ASYNC_PREWEBVIEW" in m]
        arm("50 pushes sem pagina: UMA linha, zero excepcoes",
            not raised and len(lines) == 1,
            "excepcao=%r linhas_EMIT_ASYNC_PREWEBVIEW=%d"
            % (raised or "nenhuma", len(lines)))

        # arm B -- com pagina, o script e' postado e leva o payload MAIS NOVO
        core = _Core()
        shell = _Shell(core, _WebView2())
        try:
            for i in range(5):
                mod.SottoShell.emit_async(shell, "stats", {"n": i})
            newest = bool(core.scripts) and '"n": 4' in core.scripts[-1].replace(
                '\\"', '"')
        except Exception as exc:                       # noqa: BLE001
            newest = False
            core.scripts.append("<%s: %s>" % (type(exc).__name__, exc))
        arm("com pagina o feed NAO pode ser engolido (payload mais novo)",
            newest,
            "scripts=%d ultimo=%s"
            % (len(core.scripts),
               (core.scripts[-1][:60] + "...") if core.scripts else "nenhum"))

        # arm C -- a guarda nao fecha o canal depois de a pagina existir
        shell = _Shell(None, None)
        before = 0
        try:
            mod.SottoShell.emit_async(shell, "stats", {"n": 0})
            shell.core = _Core()
            shell.webview2 = _WebView2()
            before = len(shell.core.scripts)
            mod.SottoShell.emit_async(shell, "stats", {"n": 1})
        except Exception as exc:                       # noqa: BLE001
            shell.core = getattr(shell, 'core', None) or _Core()
            shell.core.scripts.append("<%s: %s>" % (type(exc).__name__, exc))
        arm("depois de a pagina existir o mesmo kind volta a postar",
            len(shell.core.scripts) == before + 1,
            "scripts_depois=%d (antes=%d)"
            % (len(shell.core.scripts), before))

        failed = results.count(False)
        if neg:
            caught = failed > 0
            print("NEG-ARM %s: %d de %d arm(s) vermelha(s) com a guarda fora"
                  % ("PASS" if caught else "FAIL", failed, len(results)))
            return 1 if caught else 0
        print("emit-prewebview-oracle: %d PASS / %d FAIL (%d arms)  impl=%s"
              % (len(results) - failed, failed, len(results), path))
        return 0 if failed == 0 else 1
    finally:
        if tmpdir:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
