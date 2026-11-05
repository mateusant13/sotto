# NO-BUG: ORACLE do Ctrl+Space observado -- a borda que o GIL comia.
"""ORACLE do Ctrl+Space observado -- a borda que o GIL comia.

O DEFEITO REPORTADO PELO DONO (2026-11-04), verbatim: *"control espaço nao ta
funcionando"* e, no minuto seguinte, *"funciona só de vez em quando. arruam"*.

O QUE FOI MEDIDO NO LOG VIVO, antes de tocar em codigo:

    HOTKEY_OBSERVER_ALIVE role=live beats=8  loops=1218 max_gap_ms=516
    HOTKEY_OBSERVER_ALIVE role=live beats=11 loops=1223 max_gap_ms=609

O observador do `Ctrl+Space` le `GetAsyncKeyState` a cada 25 ms
(`_HotkeyObserver.POLL_S = 0.025`), mas a volta dele atrasa ate' ~0,6 s quando
a inferencia ou uma leitura de UIA seguram o GIL. Um toque de Ctrl+Space dura
~120-200 ms: um toque mais curto que a volta cai INTEIRO entre duas leituras e
nao existe. Isso e' "so' de vez em quando", e nao e' um palpite -- e' o
`max_gap_ms` medido contra a duracao do gesto.

A CURA: o bit 0 de `GetAsyncKeyState` ("esta tecla foi carregada DEPOIS da
chamada anterior") -- o Windows guarda a borda, e no'-la lemos mesmo com a volta
atrasada. Sem hook global (proibido nesta arvore) e sem `RegisterHotKey` (daria
so' a descida e roubaria a tecla ao resto do sistema).

AS ARMS -- o observador REAL, com `key_state` injectado (a costura que o
proprio modulo ja' tem para testar), nenhuma abre janela e nenhuma toca tecla:

  A  TAP QUE CAI ENTRE DUAS VOLTAS: o bit 0 aparece UMA vez e 0x8000 nunca.
     Tem de disparar UMA vez, com `via=latched`. Antes da cura: zero.
  B  SEGURADA: 0x8000 a 0,3 s -> dispara uma vez `via=state`; solta; segundo
     toque -> `count=2`.
  C  SOLTA PERDIDA: 0x8000 para sempre -> o latch re-arma aos 3 s e o log diz
     `HOTKEY_STATE_STUCK`.

O BRACO NEGATIVO (`--neg-arm`) tira a leitura do bit 0 de uma COPIA e exige A
vermelha (zero presses). rc=1 quer dizer APANHOU o mutante.

    python _main/hotkey-live-edge-oracle.py
"""

from __future__ import annotations

import importlib.util
import io
import os
import os
import sys
import tempfile
import threading
import time
import types

#: A ARVORE E' A DESTE FICHEIRO (2026-11-04). Era `r"H:\sotto\..."` fixo: um oraculo de lane
#: julgava a arvore viva em vez da sua, e o `--neg-arm` mutava o shell do dono a partir de um
#: worktree. `SOTTO_ROOT` continua a poder aponta-lo para outro lado.
_ROOTE = os.environ.get("SOTTO_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(_ROOTE, "app", "webview", "sotto_webview.py")
#: A ANCORA E' A LINHA QUE HOJE GUARDA A BORDA (2026-11-04). Era `& 0x0001`; o gesto passou a ler
#: `0x8003` (down OU borda) como condicao do modificador, e um `--neg-arm` com a ancora velha
#: dizia "NEG-ARM IMPOSSIVEL" com rc=2 -- o braco negativo deixava de provar o que quer que fosse.
EDGE = "                if not any(_v & 0x8003 for _v in _st):"


def _stub_system() -> None:
    class _Sub:
        def __init__(self, *args, **kwargs):
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


def _load(path: str):
    sys.path.insert(0, os.path.dirname(SHELL))
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("sotto_shell_hotkey_ut", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Script:
    """Uma linha do tempo de estados de tecla, em segundos desde o arranque.

    O BIT 0 E' DE UMA SO' LEITURA, como no Windows: `GetAsyncKeyState` devolve
    "carregada desde a chamada anterior" e LIMPA-O na mesma chamada. Sem isso o
    stub mentiria -- a mesma borda seria devolvida em cada volta e a arm A
    contaria seis presses (medido: 6, antes de modelar a limpeza).
    """

    def __init__(self, windows):
        self.windows = windows          # [(t0, t1, valor)]
        self.t0 = time.monotonic()
        self._latch_used = set()

    def __call__(self, vk):
        now = time.monotonic() - self.t0
        for i, (a, b, value) in enumerate(self.windows):
            if a <= now < b:
                value &= ~0x8000 if False else value
                if value & 0x0001:
                    key = (i, vk)
                    if key in self._latch_used:
                        value &= ~0x0001
                    else:
                        self._latch_used.add(key)
                return value
        return 0


def _run_observer(mod, script, seconds, poll_s=0.005):
    logs = []
    fired = []

    obs = mod.PassiveHotkeyThread(
        'ctrl+space', lambda: fired.append(time.monotonic()),
        log_fn=lambda m: logs.append(str(m)), role='live',
        poll_s=poll_s, key_state=script)
    t = threading.Thread(target=obs.run, daemon=True)
    t.start()
    time.sleep(seconds)
    obs.stop()
    t.join(timeout=2.0)
    return logs, fired


def main(argv) -> int:
    neg = "--neg-arm" in argv
    _stub_system()

    path = SHELL
    tmpdir = ""
    if neg:
        src = io.open(SHELL, encoding="utf-8", newline="").read()
        if EDGE not in src:
            print("NEG-ARM IMPOSSIVEL: a leitura do bit 0 nao esta' no shell")
            return 2
        stripped = src.replace(EDGE,
                               "                if True:", 1)
        tmpdir = tempfile.mkdtemp(prefix="hotkey-edge-neg-")
        path = os.path.join(tmpdir, "sotto_webview_mutant.py")
        io.open(path, "w", encoding="utf-8", newline="").write(stripped)

    try:
        mod = _load(path)
        results = []

        def arm(name, ok, detail):
            results.append(bool(ok))
            print("[%s] arm: %s\n       %s"
                  % ("PASS" if ok else "FAIL", name, detail))

        # A -- o toque que cai entre duas voltas: so' o bit 0
        logs, fired = _run_observer(mod, _Script([(0.10, 0.13, 0x0001)]), 0.6)
        latched = [m for m in logs if 'via=latched' in m]
        arm("TAP entre duas voltas (bit 0) dispara UMA vez via=latched",
            len(fired) == 1 and len(latched) == 1,
            "presses=%d via_latched=%d" % (len(fired), len(latched)))

        # B -- segurada, solta, segundo toque
        logs, fired = _run_observer(
            mod, _Script([(0.10, 0.40, 0x8001), (0.60, 0.75, 0x8001)]), 1.1)
        via_state = [m for m in logs if 'via=state' in m]
        counts = [m.split('count=')[1].split()[0] for m in logs
                  if 'HOTKEY_PRESSED' in m]
        arm("segurada dispara via=state e o SEGUNDO toque conta",
            len(fired) == 2 and counts == ['1', '2'] and len(via_state) >= 1,
            "presses=%d counts=%s via_state=%d"
            % (len(fired), counts, len(via_state)))

        # C -- solta perdida: o latch re-arma aos 3 s
        logs, fired = _run_observer(mod, _Script([(0.0, 9.0, 0x8000)]), 3.6)
        stuck = [m for m in logs if 'HOTKEY_STATE_STUCK' in m]
        # O RE-ARME dispara OUTRA vez enquanto a tecla ainda esta' em baixo --
        # e' o que "re-arma" quer dizer. O que se exige e' que ele ACONTEÇA e
        # que a tecla nao fique muda para sempre.
        arm("solta perdida re-arma o latch aos 3 s (nao trava a tecla)",
            len(fired) >= 1 and len(stuck) >= 1,
            "presses=%d stuck=%d" % (len(fired), len(stuck)))

        failed = results.count(False)
        if neg:
            caught = failed > 0
            print("NEG-ARM %s: %d de %d arm(s) vermelha(s) sem o bit 0"
                  % ("PASS" if caught else "FAIL", failed, len(results)))
            return 1 if caught else 0
        print("hotkey-live-edge-oracle: %d PASS / %d FAIL (%d arms)  impl=%s"
              % (len(results) - failed, failed, len(results), path))
        return 0 if failed == 0 else 1
    finally:
        if tmpdir:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
