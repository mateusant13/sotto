#!/usr/bin/env python
# NO-BUG: conduz o `_on_silence` REAL com um shell falso; nao reproduz a corrida de 17 ms do log do dono nem o respawn de 61,8 s.
"""O CAO DE GUARDA NAO MATA COM A PROVA DE VIDA EM VOO.

DEFEITO MEDIDO, no log do dono (`_main/webview-run.log`, 2026-11-09):

    15:44:36.228  BRIDGE_SILENT ms=30000 pid=54592
    15:44:36.245  BRIDGE_ALIVE WORKER_ALIVE seq=3944 phase=window age_ms=39657
    15:44:37.465  BRIDGE_SPAWNED pid=47096 ...
    15:45:39.038  BRIDGE_LOAD_MS ms=61781 pid=47096

Dezassete milissegundos: o worker estava VIVO, o batimento estava a atravessar o
cano, e o temporizador de 30 s decidiu sem lhe perguntar nada. O respawn custou
**61,8 s** a reler 1,9 GB -- o pico que o watcher de stutter atribuiu a esta
arvore no mesmo minuto.

AS ARMS, todas contra o `WorkerBridge._on_silence` REAL (nenhuma linha de texto
e' lida: um `grep` diria que a graça existe mesmo num ramo que nunca corre):

  A1  primeiro disparo (sem marco)   -> NAO mata; arma a graça (10% da janela,
                                        `silence_grace_s`) e grava o progresso de
                                        agora no marco.
  A2  segundo disparo, progresso AVANCOU -> NAO mata; devolve a janela INTEIRA
                                        (`_arm_silence`) e limpa o marco -- e' o
                                        caso do log acima.
  A3  segundo disparo, progresso PARADO   -> mata, como sempre, com
                                        `reason=silent` (o cao continua a ser um
                                        cao: um filho que trava nao ganha
                                        reprieve).
  A4  ramo BENIGNO (`no_audio`)      -> nao mata, nao arma graça nenhuma e
                                        re-arma a janela: a graça nao pode
                                        ter-se infiltrado na cura de 2026-10-15.
  A5  a RELACAO que outro portao prende continua de pe: `WORKER_SILENCE_MS` e'
                                        30000 e a graça e' menor que a janela
                                        (uma graça maior seria uma janela nova
                                        escrita por acidente).

`--neg-arm` escreve uma COPIA do shell sem o bloco da graça e exige A2 vermelha
(o codigo de "apanhado" e' 1).
"""
import argparse
import io
import os
import re
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


def _load(path, name):
    dirname = os.path.dirname(path)
    if dirname not in sys.path:
        sys.path.insert(0, dirname)
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeTimer(object):
    made = []

    def __init__(self, interval, function):
        self.interval = interval
        self.function = function
        self.daemon = False
        FakeTimer.made.append(self)

    def start(self):
        pass

    def cancel(self):
        pass


class FakeChild(object):
    pid = 4242


def _bridge(mod, *, mark, progress, no_audio=False, verdict_at=0.0):
    """A `WorkerBridge` with ONLY what `_on_silence` reads."""
    b = mod.WorkerBridge.__new__(mod.WorkerBridge)
    b.stopped = False
    b.child = FakeChild()
    b.no_audio = no_audio
    b.no_audio_evidence = {'state': 'silent-device'}
    b.no_audio_evidence_at = verdict_at
    b.pending_error = None
    b.loaded = True
    b.silence_ms = mod.WORKER_SILENCE_MS
    b.load_silence_ms = mod.WORKER_LOAD_SILENCE_MS
    b.spawned_at = 0.0
    b.last_progress_at = progress
    b._silence_mark_at = mark
    b._silence_timer = None
    b.restarts = 0
    b.lines = []
    b.killed = []
    b.armed = [0]
    b.log = lambda text: b.lines.append(str(text))
    b._status = lambda *a, **k: None
    b._bridge_status = lambda *a, **k: None
    b._kill_and_restart = lambda why, *a, **k: b.killed.append(why)
    b._arm_silence = lambda: b.armed.__setitem__(0, b.armed[0] + 1)
    return b


def run(mod):
    """Returns (ok, rows). `rows` carries why each arm passed or failed."""
    rows = []

    def arm(name, cond, detail):
        rows.append((name, bool(cond), detail))

    # A5 first: the constants, so a broken relation fails the same run.
    arm('A5-relation',
        mod.WORKER_SILENCE_MS == 30000
        and 0 < mod.silence_grace_s(mod.WORKER_SILENCE_MS)
        < (mod.WORKER_SILENCE_MS / 1000.0),
        'silence_ms=%r grace_s=%r' % (mod.WORKER_SILENCE_MS,
                                      mod.silence_grace_s(mod.WORKER_SILENCE_MS)))

    real_timer = threading.Timer
    try:
        threading.Timer = FakeTimer

        # A1 -- primeiro disparo: pergunta, nao mata.
        FakeTimer.made = []
        b = _bridge(mod, mark=None, progress=100.0)
        b._on_silence()
        arm('A1-asks-before-killing',
            not b.killed and b._silence_mark_at == 100.0
            and len(FakeTimer.made) == 1
            and abs(FakeTimer.made[0].interval
                    - mod.silence_grace_s(b.silence_ms)) < 1e-9
            and any('BRIDGE_SILENT_WAIT' in t for t in b.lines),
            'killed=%r mark=%r timers=%r lines=%r'
            % (b.killed, b._silence_mark_at, [t.interval for t in FakeTimer.made],
               b.lines[-1:] if b.lines else []))

        # A2 -- o caso do log: o progresso avancou durante a graça.
        FakeTimer.made = []
        b = _bridge(mod, mark=100.0, progress=101.0)
        b._on_silence()
        arm('A2-progress-in-flight-spares-the-worker',
            not b.killed and b.armed[0] == 1 and b._silence_mark_at is None
            and any('BRIDGE_SILENT_GRACE' in t for t in b.lines),
            'killed=%r armed=%r mark=%r lines=%r'
            % (b.killed, b.armed[0], b._silence_mark_at,
               b.lines[-1:] if b.lines else []))

        # A3 -- progresso PARADO: o cao continua a ser um cao.
        FakeTimer.made = []
        b = _bridge(mod, mark=100.0, progress=100.0)
        b._on_silence()
        arm('A3-still-silence-still-kills',
            b.killed == ['silent'] and b.armed[0] == 0
            and any('BRIDGE_SILENT ' in t for t in b.lines),
            'killed=%r armed=%r lines=%r'
            % (b.killed, b.armed[0], b.lines[-1:] if b.lines else []))

        # A4 -- o ramo benigno, COM a prova de vida (D-18): o veredicto veio em
        # 100.0 e o worker BATEU depois (104.0) -- parqueado de proposito.
        FakeTimer.made = []
        b = _bridge(mod, mark=100.0, progress=104.0, no_audio=True,
                    verdict_at=100.0)
        b._on_silence()
        arm('A4-benign-when-the-heartbeat-advanced',
            not b.killed and b.armed[0] == 1 and not FakeTimer.made
            and any('BRIDGE_SILENT_BENIGN ms=' in t for t in b.lines),
            'killed=%r armed=%r timers=%r lines=%r'
            % (b.killed, b.armed[0], len(FakeTimer.made),
               b.lines[-1:] if b.lines else []))

        # A6 -- D-18: o worker NAO bateu desde o veredicto. O ramo benigno
        # deixa de ser benigno e a PERGUNTA da graca acontece (o cao volta).
        FakeTimer.made = []
        b = _bridge(mod, mark=None, progress=100.0, no_audio=True,
                    verdict_at=100.0)
        b._on_silence()
        arm('A6-stale-verdict-asks-the-watchdog',
            not b.killed and b._silence_mark_at == 100.0
            and len(FakeTimer.made) == 1
            and any('BRIDGE_SILENT_BENIGN_STALE' in t for t in b.lines)
            and any('BRIDGE_SILENT_WAIT' in t for t in b.lines),
            'killed=%r mark=%r timers=%r lines=%r'
            % (b.killed, b._silence_mark_at, len(FakeTimer.made),
               b.lines[-2:] if b.lines else []))

        # A7 -- D-18, segundo disparo: nada desde o veredicto e nada desde a
        # pergunta -> MATA. E' o que o comentario prometia e o codigo nao fazia.
        FakeTimer.made = []
        b = _bridge(mod, mark=100.0, progress=100.0, no_audio=True,
                    verdict_at=100.0)
        b._on_silence()
        arm('A7-stale-verdict-still-kills',
            b.killed == ['silent'] and b.armed[0] == 0
            and any('BRIDGE_SILENT ' in t for t in b.lines),
            'killed=%r armed=%r lines=%r'
            % (b.killed, b.armed[0], b.lines[-1:] if b.lines else []))
    finally:
        threading.Timer = real_timer

    ok = all(cond for _name, cond, _detail in rows)
    return ok, rows


GRACE_BLOCK = (
    "        _mark = getattr(self, '_silence_mark_at', None)\n"
)


def neg_arm(src):
    """Copia do shell com o bloco da graça ARRANCADO (mutacao cirurgica)."""
    start = src.find(GRACE_BLOCK)
    if start < 0:
        raise SystemExit('NEG-ARM IMPOSSIVEL: o bloco da graca nao esta la')
    end = src.find("        self.log(f'BRIDGE_SILENT ms=", start)
    if end < 0:
        raise SystemExit('NEG-ARM IMPOSSIVEL: a linha de BRIDGE_SILENT nao esta la')
    # A mutacao mantem a LINHA de referencia (o defeito e' a ausencia da
    # pergunta, nao do log) e arranca so' a decisao.
    doomed = src[start:end]
    if 'silence_grace_s' not in doomed:
        raise SystemExit('NEG-ARM IMPOSSIVEL: o intervalo mutado nao contem a graca')
    return src[:start] + src[end:]


BENIGN_BLOCK_START = "            _progress = getattr(self, 'last_progress_at', None)"
BENIGN_BLOCK_END = "            # desfecho quando o progresso nao andou.\n"


def neg_arm_benign(src):
    """D-18: repoe o ramo benigno que re-arma e RETORNA sem perguntar nada.

    A mutacao cirurgica e' a cura ao contrario -- o comentario prometia um cao
    de guarda e o codigo antigo devolvia sempre.
    """
    start = src.find(BENIGN_BLOCK_START)
    if start < 0:
        raise SystemExit('NEG-ARM IMPOSSIVEL: o bloco do D-18 nao esta la')
    end = src.find(BENIGN_BLOCK_END, start)
    if end < 0:
        raise SystemExit('NEG-ARM IMPOSSIVEL: a cauda do bloco do D-18 nao esta la')
    end += len(BENIGN_BLOCK_END)
    return (src[:start]
            + "            self._arm_silence()\n"
              "            return\n"
            + src[end:])


MUTANTS = (
    ('nograce', 'grace-block-removed', neg_arm, '_sotto_webview_nograce.py'),
    ('benign', 'benign-returns-without-asking', neg_arm_benign,
     '_sotto_webview_benignreturn.py'),
)


def _load_mutant(tag, name, maker):
    """Carrega um mutante com as ancoras normalizadas para LF.

    AS ANCORAS SAO ESCRITAS COM LF E O SHELL E CRLF: sem normalizar, o
    `find(GRACE_BLOCK)` devolvia -1 e o `--neg-arm` morria em
    `NEG-ARM IMPOSSIVEL` -- um controlo que nao corria (medido 2026-11-12).
    """
    src = io.open(SHELL, 'r', encoding='utf-8', newline='').read()
    src = src.replace('\r\n', '\n')
    mutant = maker(src)
    # O mutante vive AO LADO do original: o modulo importa irmaos por nome
    # (`import hot_reload`), e uma copia em `_main/_cache` morre em
    # `ModuleNotFoundError` antes de qualquer arm correr.
    tmp = os.path.join(os.path.dirname(SHELL), name)
    io.open(tmp, 'w', encoding='utf-8', newline='\n').write(mutant)
    try:
        return _load(tmp, 'sotto_webview_%s' % tag)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)

    if not args.neg_arm:
        mod = _load(SHELL, 'sotto_webview')
        ok, rows = run(mod)
        for name, cond, detail in rows:
            print('%-42s %s   %s' % (name, 'PASS' if cond else 'FAIL', detail))
        print('VERDICT: %s -- %d/%d arms'
              % ('PASS' if ok else 'FAIL',
                 sum(1 for _n, c, _d in rows if c), len(rows)))
        return 0 if ok else 1

    caught_any = False
    for tag, what, maker, name in MUTANTS:
        mod = _load_mutant(tag, name, maker)
        ok, rows = run(mod)
        for name_, cond, detail in rows:
            print('%-42s %s   %s' % (name_, 'PASS' if cond else 'FAIL', detail))
        caught = [n for n, cond, _d in rows if not cond]
        if caught:
            caught_any = True
            print('NEG-ARM MUTANT %s (%s): PASS -- %d/%d arms ainda passam; '
                  'vermelhas: %s'
                  % (tag, what, len(rows) - len(caught), len(rows),
                     ', '.join(caught)))
        else:
            print('NEG-ARM MUTANT %s (%s): FAIL -- passou as %d arms'
                  % (tag, what, len(rows)))
        print('')
    if caught_any:
        print('NEG-ARM: PASS -- %d/%d mutantes apanhados' % (
            sum(1 for t, _w, _m, _n in MUTANTS), len(MUTANTS)))
        return 1
    print('NEG-ARM: FAIL -- nenhum mutante foi apanhado')
    return 0


if __name__ == '__main__':
    sys.exit(main())
