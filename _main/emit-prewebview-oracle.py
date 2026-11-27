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


class _DeferredShell(_Shell):
    """`_post` que GUARDA o callable: e' a janela em que dois pushes se cruzam."""

    def __init__(self, core, webview2):
        super().__init__(core, webview2)
        self.queued = []

    def _post(self, fn):
        self.queued.append(fn)
        return True

    def drain(self):
        while self.queued:
            self.queued.pop(0)()


def _load(path):
    # o mutante vive num tmpdir e importa os irmaos do shell (`hot_reload`,
    # `panel_state`): o diretorio REAL fica no caminho nos dois casos.
    sys.path.insert(0, os.path.dirname(SHELL))
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("sotto_shell_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _kill_core_guard(src):
    """Remove SO' a guarda `core is None` de `exec_js_post`, deixando `emit_async`.

    O shell e' CRLF no disco e o oraculo le' com newline universal; a ancora e'
    escrita em `\n` e comparada DEPOIS da mesma normalizacao, senao a mutacao
    "nao muda o ficheiro" e o mutante passa por engano (medido 2026-11-27: foi
    exactamente o que aconteceu na primeira versao deste helper).
    """
    text = src.replace("\r\n", "\n")
    old = ("            core = self.core\n"
           "            if core is None:\n")
    new = ("            core = self.core\n"
           "            if False and core is None:\n")
    if text.count(old) != 1:
        return src
    return text.replace(old, new, 1)


def _arms(path):
    """As seis arms sobre `path`. Devolve [(nome, ok, detalhe)] e NAO imprime."""
    _stub_system()
    mod = _load(path)
    captured = []
    mod.log = lambda msg: captured.append(str(msg))
    mod.warn = lambda msg: captured.append('WARN ' + str(msg))
    results = []

    def arm(name, ok, detail):
        results.append((name, bool(ok), detail))

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

    # arm D -- A OUTRA PORTA DO MESMO DEFEITO (2026-11-27): `exec_js_post` era a
    # unica metade sem a guarda, e o log do dono mostra as CINCO linhas dela no
    # arranque (11:45:11.272-279): `WARN exec_js_post failed: AttributeError`'NoneType'
    # object has no attribute 'ExecuteScriptAsync'``. Um aviso por emit e' a mesma
    # doenca do arm A, na porta ao lado.
    shell = _Shell(None, None)
    del captured[:]
    raised_d = ""
    for _ in range(50):
        try:
            mod.SottoShell.exec_js_post(shell, "window.__x=1")
        except Exception as exc:                   # noqa: BLE001
            raised_d = "%s: %s" % (type(exc).__name__, exc)
            break
    # `_Shell._post` corre o callable INLINE (e' o que a UI thread faria), logo
    # nao ha' fila a drenar aqui -- `_DeferredShell` e' que a guarda.
    deferred = [m for m in captured if "EXEC_JS_DEFERRED" in m]
    warns = [m for m in captured if "exec_js_post failed" in m]
    arm("exec_js_post sem pagina: UMA linha, ZERO WARN por emit",
        not raised_d and len(deferred) == 1 and not warns,
        "excepcao=%r EXEC_JS_DEFERRED=%d warns=%d"
        % (raised_d or "nenhuma", len(deferred), len(warns)))

    # arm E -- e com pagina o script E' postado (a guarda nao engole o canal)
    core = _Core()
    shell = _Shell(core, _WebView2())
    ok_e = bool(mod.SottoShell.exec_js_post(shell, "window.__y=2"))
    arm("exec_js_post com pagina posta o script",
        ok_e and core.scripts and core.scripts[-1] == "window.__y=2",
        "postado=%r scripts=%d" % (ok_e, len(core.scripts)))

    # arm D -- DUAS legendas na janela de um so' drain: as DUAS chegam, na
    # ordem. Uma legenda e' EVENTO (e' a pagina que a commita ao historico);
    # colapsa-la perde fala sem uma linha no log.
    core = _Core()
    shell = _DeferredShell(core, _WebView2())
    queued_before = 0
    try:
        mod.SottoShell.emit_async(shell, "caption", {"text": "A"})
        mod.SottoShell.emit_async(shell, "caption", {"text": "B"})
        queued_before = len(shell.queued)
        shell.drain()
        texts = [sc for sc in core.scripts if 'caption' in sc]
        plain = [t.replace('\\"', '"') for t in texts]
        both = (len(plain) == 2 and '"A"' in plain[0]
                and '"B"' in plain[1])
    except Exception as exc:                       # noqa: BLE001
        both = False
        core.scripts.append("<%s: %s>" % (type(exc).__name__, exc))
    arm("duas legendas antes do drain: as DUAS chegam, na ordem",
        both,
        "queued=%d scripts=%d caudas=%r"
        % (queued_before, len(core.scripts),
           [t[-26:] for t in core.scripts]))

    # arm E -- o FEED continua a colapsar: duas amostras = UM script, a mais
    # nova. A cura dos eventos nao pode ter desfeito o tecto que o latch
    # existe para dar (43 amostras/s medidas nesta maquina).
    core = _Core()
    shell = _DeferredShell(core, _WebView2())
    try:
        mod.SottoShell.emit_async(shell, "stats", {"n": 0})
        mod.SottoShell.emit_async(shell, "stats", {"n": 1})
        shell.drain()
        collapsed = (len(core.scripts) == 1
                     and '"n": 1' in core.scripts[0].replace('\\"', '"'))
    except Exception as exc:                       # noqa: BLE001
        collapsed = False
        core.scripts.append("<%s: %s>" % (type(exc).__name__, exc))
    arm("o feed de estado CONTINUA a colapsar (um script, o mais novo)",
        collapsed,
        "scripts=%d ultimo=%s"
        % (len(core.scripts),
           (core.scripts[-1][:60] + "...") if core.scripts else "nenhum"))

    # arm F -- a fila de eventos tem TECTO e o que a excede e' CONTADO e
    # DITO: 40 legendas com a pagina parada = 32 entregues + uma linha
    # `CAPTION_EMIT_DROPPED ... n=8`. Sem esta arm o tecto podia cortar em
    # silencio, que e' a mesma doenca noutro sitio.
    core = _Core()
    shell = _DeferredShell(core, _WebView2())
    before = len(captured)
    try:
        for i in range(40):
            mod.SottoShell.emit_async(shell, "caption", {"text": "C%d" % i})
        shell.drain()
        dropped = [m for m in captured[before:]
                   if "CAPTION_EMIT_DROPPED" in m]
        capped = (len(core.scripts) == 32 and len(dropped) == 1
                  and "n=8" in dropped[0])
    except Exception as exc:                       # noqa: BLE001
        capped = False
        core.scripts.append("<%s: %s>" % (type(exc).__name__, exc))
    arm("40 legendas com a pagina parada: 32 entregues e n=8 DITO",
        capped,
        "scripts=%d dropped=%r"
        % (len(core.scripts),
           [m for m in captured[before:] if "CAPTION_EMIT_DROPPED" in m][:1]))


    return results


def main(argv) -> int:
    """O positivo corre as seis arms no ficheiro vivo; o negativo exige que CADA
    mutante derrube as arms que o nomeiam.

    Medido 2026-11-12: o negativo desta casa devolvia 1 quando apanhava, mas um
    mutante NOVO (o latch a colapsar legendas) passava despercebido porque o
    unico mutante era a guarda do `core`. Um controlo que so' conhece o defeito
    de ontem certifica o defeito de hoje.
    """
    neg = "--neg-arm" in argv
    tmpdirs = []
    try:
        if neg:
            src = io.open(SHELL, encoding="utf-8", newline="").read()
            _eol = "\r\n" if "\r\n" in src else "\n"
            guard = "if self.core is None or self.webview2 is None:" + _eol
            events = "if kind in EVENT_EMIT_KINDS:" + _eol
            if GUARD + _eol not in src or events not in src:
                print("NEG-ARM IMPOSSIVEL: a guarda ou o ramo dos eventos "
                      "nao esta' no shell (o oraculo envelheceu)")
                return 2
            # o mutante MANTEM a estrutura e desliga a CONDICAO: trocar a linha
            # por `pass` deixava o corpo do `if` sem pai (IndentationError).
            mutants = [
                ("guarda-removida",
                 src.replace(guard,
                             "if False and (self.core is None or "
                             "self.webview2 is None):" + _eol, 1),
                 ("50 pushes sem pagina",)),
                ("evento-colapsado",
                 src.replace(events, "if False and kind in "
                             "EVENT_EMIT_KINDS:" + _eol, 1),
                 ("duas legendas antes do drain",
                  "40 legendas com a pagina parada")),
                # M3 (2026-11-27): a guarda que este oraculo passou a exigir em
                # `exec_js_post` -- a porta que continuava sem ela. Sem este
                # mutante, as arms D/E de hoje mediriam o codigo sem uma foto
                # dos bytes de antes.
                ("sem-guarda-no-exec-js-post",
                 _kill_core_guard(src),
                 ("exec_js_post sem pagina",)),
            ]
            for label, text, must_fail in mutants:
                if text == src:
                    print("NEG-ARM IMPOSSIVEL[%s]: a mutacao nao mudou o "
                          "ficheiro" % label)
                    return 2
                d = tempfile.mkdtemp(prefix="emit-prewebview-neg-")
                tmpdirs.append(d)
                path = os.path.join(d, "sotto_webview_mutant.py")
                io.open(path, "w", encoding="utf-8",
                        newline="").write(text)
                results = _arms(path)
                red = [name for name, ok, _detail in results if not ok]
                hit = [want for want in must_fail
                       if any(want in name for name in red)]
                print("NEG-ARM[%s]: %d de %d arm(s) vermelha(s); esperadas=%r "
                      "apanhadas=%r" % (label, len(red), len(results),
                                        list(must_fail), hit))
                if len(hit) != len(must_fail):
                    print("NEG-ARM FAIL[%s]: o mutante sobreviveu" % label)
                    return 0
            print("NEG-ARM PASS: %d de %d mutante(s) apanhado(s) pela SUA arm"
                  % (len(mutants), len(mutants)))
            return 1
        results = _arms(SHELL)
        for name, ok, detail in results:
            print("[%s] arm: %s\n       %s"
                  % ("PASS" if ok else "FAIL", name, detail))
        failed = [name for name, ok, _d in results if not ok]
        print("emit-prewebview-oracle: %d PASS / %d FAIL (%d arms) impl=%s"
              % (len(results) - len(failed), len(failed), len(results), SHELL))
        return 0 if not failed else 1
    finally:
        if tmpdirs:
            import shutil
            for d in tmpdirs:
                shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
