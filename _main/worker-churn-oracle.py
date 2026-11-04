"""O oracle do CHURN DE RECARGA: o shell mata um worker que esta' quieto, e
recarrega-o dois segundos depois de uma saida limpa.

AS DUAS METIDAS QUE O JUSTIFICAM (log do dono, 2026-11-04):

  03:18:03  BRIDGE_SPAWNED pid=26440
  03:20:13  BRIDGE_SILENT ms=30000 pid=26440
  03:20:14  BRIDGE_KILLED pid=26440 rc=1 why=the-shell-terminated-it
  03:20:14  BRIDGE_SPAWNED pid=17044        <- 1,9 GB de modelo recarregado
  03:22:41  BRIDGE_EXIT pid=17044 rc=0 killed=False
  03:22:43  BRIDGE_SPAWNED pid=37212        <- 2,0 s: outra recarga completa

O tap aberto sobre uma maquina QUIETA nao escreve nada por desenho
(`endpoint-idle` -> `stop.wait(0.1)`), e `WORKER_STATS` nao conta enquanto
`blocks` nao avanca. O worker passou a publicar `WORKER_ALIVE` a partir do laco
(prova de progresso, nao de liveness: cala-se quando o laco trava), e uma saida
`rc=0` -- o worker que terminou por vontade propria -- deixou de ser um crash
respondido em 1 s.

O QUE ESTE FICHEIRO EXECUTA, e nao copia:

  arm 1  `WorkerBridge._schedule_restart` REAL, com `floor_ms=CLEAN_EXIT_FLOOR_MS`
         -> o temporizador e' armado com o piso (20 000 ms), nao com 1 000.
  arm 2  a MESMA funcao sem piso (o caminho do crash `rc != 0`) -> 1 000 ms, e o
         piso NAO aparece no log. Um piso que se aplica a tudo nao e' um piso.
  arm 3  a REGRA DO LEITOR (`line.startswith(PROGRESS_TAGS)`) sobre a linha que o
         worker escreve de facto: `WORKER_ALIVE ...` conta como progresso e
         `BRIDGE_METER ...` (o batimento do painel, que nao prova laco) nao conta.
  arm 4  o worker REAL carregado por caminho: `progress()` move o seq, e o texto
         que o batimento publica e' o que a arm 3 le.

`--neg-arm` muta uma COPIA do shell (o piso removido) e exige a arm 1 RED, e muta
uma COPIA do worker (o emissor do batimento fixo) e exige a arm 4 RED.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')


for _d in (os.path.join(ROOT, 'app', 'webview'), os.path.join(ROOT, 'worker')):
    if _d not in sys.path:
        sys.path.insert(0, _d)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeTimer:
    """Um `threading.Timer` que nao dispara: so' regista o intervalo armado."""

    armed = []

    def __init__(self, interval, function, args=None, kwargs=None):
        self.interval = interval
        self.function = function
        FakeTimer.armed.append(interval)

    def start(self):
        pass

    def cancel(self):
        pass


def bridge_stub(mod, sink):
    """Um `WorkerBridge` sem __init__: os atributos que `_schedule_restart` le',
    e o metodo REAL a correr por cima deles."""
    b = object.__new__(mod.WorkerBridge)
    b.stopped = False
    b.restarts = 0
    b.no_audio_restarts = 0
    b.backoff_base = 1000
    b.backoff_max = 30000
    b.no_audio_backoff_base = 15000
    b.no_audio_backoff_max = 300000
    b.no_audio_restart_cap = 3
    b._restart_timer = None
    b._restart = lambda: None
    b._arm_audio_resume = lambda *a, **k: None
    b.log = sink
    return b


def judge(shell_mod, worker_mod, quiet=False):
    """Devolve (checks, ok). `checks` e' a lista que o `--neg-arm` re-le'."""
    checks = []

    def check(name, cond, detail):
        checks.append({'arm': name, 'ok': bool(cond), 'detail': detail})

    # -- arm 1 + arm 2: o piso da saida limpa, pelo metodo real ----------------
    FakeTimer.armed = []
    shell_mod.threading.Timer = FakeTimer
    logs = []
    b = bridge_stub(shell_mod, logs.append)
    b._schedule_restart('exit', no_audio=False,
                        floor_ms=shell_mod.CLEAN_EXIT_FLOOR_MS)
    floor_log = '\n'.join(logs)
    armed_floor = FakeTimer.armed[-1] * 1000.0 if FakeTimer.armed else None
    check('1-floor-on-clean-exit',
          armed_floor == float(shell_mod.CLEAN_EXIT_FLOOR_MS)
          and 'BRIDGE_RESTART_FLOOR' in floor_log
          and f'in_ms={shell_mod.CLEAN_EXIT_FLOOR_MS}' in floor_log,
          {'armed_ms': armed_floor, 'floor': shell_mod.CLEAN_EXIT_FLOOR_MS,
           'log': floor_log.strip().splitlines()[-1:] if floor_log else []})

    FakeTimer.armed = []
    logs = []
    b = bridge_stub(shell_mod, logs.append)
    b._schedule_restart('exit', no_audio=False)          # o caminho do crash
    crash_log = '\n'.join(logs)
    armed_crash = FakeTimer.armed[-1] * 1000.0 if FakeTimer.armed else None
    check('2-no-floor-on-crash',
          armed_crash == 1000.0 and 'BRIDGE_RESTART_FLOOR' not in crash_log,
          {'armed_ms': armed_crash, 'log': crash_log.strip().splitlines()[-1:]})

    # -- arm 3: a regra do leitor sobre a linha que o worker escreve ----------
    # A shell reconhece o batimento por `is_alive_beat` (CONTER, nao comecar):
    # medido com o py-spy, o fio batia `seq=516` e a linha chegava precedida do
    # lixo WIDESTRING do ONNX, por isso `startswith` perdia-a.
    beat = 'WORKER_ALIVE seq=7 phase=idle-wait age_ms=12'
    garbled = "\u1b00\u5b00\u3000\u3b00" + beat
    meter = 'BRIDGE_METER count=2230 in_window_s=30.0'
    check('3-reader-counts-the-beat',
          shell_mod.is_alive_beat(beat) and shell_mod.is_alive_beat(garbled),
          {'beat': beat, 'garbled': garbled[:40],
           'startswith_would_miss': not garbled.startswith('WORKER_ALIVE')})
    check('3b-reader-ignores-the-meter',
          not shell_mod.is_alive_beat(meter),
          {'meter': meter})

    # -- arm 4: o laco do worker REAL move o seq ------------------------------
    before = worker_mod.PROGRESS['seq']
    worker_mod.progress('idle-wait')
    after = worker_mod.PROGRESS['seq']
    check('4-worker-progress-moves',
          after == before + 1 and worker_mod.PROGRESS['phase'] == 'idle-wait',
          {'before': before, 'after': after,
           'phase': worker_mod.PROGRESS['phase']})

    # -- arm 5: a guarda da ESPERA (so' quando nada podia ter sido capturado) --
    sh = worker_mod.should_hold
    guard = {
        'exhausted-waiting': sh('rotation-ceiling', 0, False),
        'all-flat-waiting': sh('all-flat', 0, False),
        'captions-no-wait': sh('rotation-ceiling', 3, False),
        'stop-no-wait': sh('rotation-ceiling', 0, True),
        'healthy-no-wait': sh('streaming', 0, False),
    }
    check('5-hold-only-when-nothing-captured',
          guard['exhausted-waiting'] and guard['all-flat-waiting']
          and not guard['captions-no-wait'] and not guard['stop-no-wait']
          and not guard['healthy-no-wait'], guard)

    class FakeStop:
        def __init__(self, set_after=None):
            self.n = 0
            self.set_after = set_after
            self._set = False

        def is_set(self):
            return self._set

        def set(self):
            self._set = True

        def wait(self, t):
            # O RELOGIO TEM DE ANDAR: sem o `sleep` este laco gira a vapor e um
            # mutante que desliga a comparacao do censo so' cai ao fim de
            # `max_hold_s` -- o braco negativo ficava 600 s a girar (medido).
            time.sleep(min(t, 0.002))
            self.n += 1
            if self.set_after is not None and self.n >= self.set_after:
                self._set = True
                return True
            return False

    def run_hold(census, set_after=None, max_hold_s=1.0, poll_s=0.01):
        seen = []
        stop = FakeStop(set_after=set_after)
        seq_before = worker_mod.PROGRESS['seq']
        reason = worker_mod.hold_idle_slot(
            stop, lambda **kw: seen.append(kw), census, 'rotation-ceiling',
            max_hold_s=max_hold_s, poll_s=poll_s)
        return reason, seen, stop, worker_mod.PROGRESS['seq'] - seq_before

    # -- arm 6: um dispositivo a aparecer ACABA a espera ----------------------
    calls = {'n': 0}

    def growing():
        calls['n'] += 1
        return ['VoiceMeeter Input'] if calls['n'] < 2 else ['VoiceMeeter Input', 'Headset']

    reason6, seen6, stop6, seq6 = run_hold(growing)
    check('6-hold-ends-on-census-change',
          reason6 == 'census-changed'
          and [e.get('state') for e in seen6] == ['worker-idle', 'worker-idle-end']
          and seen6[0].get('reason') == 'rotation-ceiling'
          and seq6 >= 1,
          {'reason': reason6, 'states': [e.get('state') for e in seen6], 'seq_moved': seq6})

    # -- arm 7: o dono pedir parada acaba a espera ----------------------------
    reason7, seen7, stop7, _ = run_hold(lambda: ['A'], set_after=1)
    check('7-hold-ends-on-stop', reason7 == 'stopped' and len(seen7) == 2,
          {'reason': reason7, 'states': [e.get('state') for e in seen7]})

    # -- arm 8: a espera TEM FIM (nao e' um processo pendurado) --------------
    reason8, seen8, stop8, _ = run_hold(lambda: ['A'], max_hold_s=0.05, poll_s=0.01)
    end8 = seen8[-1] if seen8 else {}
    check('8-hold-expires', reason8 == 'hold-expired' and end8.get('held_s', 0) >= 0.05,
          {'reason': reason8, 'held_s': end8.get('held_s'), 'polls': stop8.n})

    # -- arm 9: a espera MANTEM O BATIMENTO A ANDAR --------------------------
    check('9-hold-keeps-the-beat-moving',
          worker_mod.PROGRESS['phase'] == 'idle-wait',
          {'phase': worker_mod.PROGRESS['phase']})

    # -- arm 10: a espera esta' LIGADA ao caminho do teto (nao so' escrita) --
    # O FICHEIRO DO MODULO CARREGADO, nao o do repo: o `--neg-arm` corre sobre uma
    # COPIA mutada, e ler o original deixava o mutante sobreviver (medido).
    src = io.open(getattr(worker_mod, '__file__', WORKER), encoding='utf-8', newline='').read()
    call = "if should_hold(outcome, counters['captions'], stop.is_set()):"
    i_call = src.find(call)
    i_hold = src.find('outcome = hold_idle_slot(', i_call + 1) if i_call >= 0 else -1
    # o `except` que fecha o `try` do run: a chamada tem de estar DENTRO dele
    i_except = src.find('    except KeyboardInterrupt:', i_call + 1) if i_call >= 0 else -1
    wired = (i_call > 0 and i_hold > i_call and 0 < i_except and i_call < i_except)
    check('10-hold-is-wired-into-the-ceiling-path', wired,
          {'call_at': i_call, 'hold_at': i_hold, 'except_at': i_except})

    ok = all(c['ok'] for c in checks)
    return checks, ok


def mutate_shell(dst):
    """Tira o piso do caminho da saida limpa E a regra do batimento
    (as arms 1 e 3 tem de cair)."""
    src = io.open(SHELL, encoding='utf-8', newline='').read()
    out = src.replace('if floor_ms and delay < floor_ms:', 'if False:', 1)
    assert out != src, 'a ancora do piso nao existe'
    src, out = out, out.replace("    return 'WORKER_ALIVE' in line", '    return False', 1)
    assert out != src, 'a ancora do is_alive_beat nao existe'
    io.open(dst, 'w', encoding='utf-8', newline='').write(out)


def mutate_worker(dst):
    """Tres mutacoes no worker: o `progress` parado (arm 4), a guarda da espera
    desligada (arm 5) e o censo a nunca diferir (arm 6)."""
    src = io.open(WORKER, encoding='utf-8', newline='').read()
    out = src.replace("        PROGRESS['seq'] += 1\r\n", "", 1)
    assert out != src, 'a ancora do progress nao existe'
    src, out = out, out.replace("    return outcome in ('rotation-ceiling', 'all-flat', 'open-failed', 'explicit-flat')", '    return False', 1)
    assert out != src, 'a ancora do should_hold nao existe'
    src, out = out, out.replace("        if base is not None and now is not None and now != base:", '        if False:', 1)
    assert out != src, 'a ancora do censo nao existe'
    src, out = out, out.replace("        if should_hold(outcome, counters['captions'], stop.is_set()):", '        if False:', 1)
    assert out != src, 'a ancora da fiacao da espera nao existe'
    io.open(dst, 'w', encoding='utf-8', newline='').write(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta copias do shell e do worker e exige as arms RED')
    args = ap.parse_args(argv)

    if args.neg_arm:
        tmp = tempfile.mkdtemp(prefix='churn-neg-')
        sh = os.path.join(tmp, 'sotto_webview_mut.py')
        wk = os.path.join(tmp, 'sotto_worker_mut.py')
        mutate_shell(sh)
        mutate_worker(wk)
        shell_mod = load(sh, 'shell_mut')
        # o worker mutado importa o irmao por nome: o repo tem de estar no path
        sys.path.insert(0, os.path.join(ROOT, 'worker'))
        worker_mod = load(wk, 'worker_mut')
        checks, ok = judge(shell_mod, worker_mod, quiet=True)
        red = [c['arm'] for c in checks if not c['ok']]
        caught = ('1-floor-on-clean-exit' in red and '4-worker-progress-moves' in red
                  and '3-reader-counts-the-beat' in red
                  and '5-hold-only-when-nothing-captured' in red
                  and '6-hold-ends-on-census-change' in red
                  and '10-hold-is-wired-into-the-ceiling-path' in red)
        print(f'NEG-ARM arms={len(checks)} caidas={red}')
        for c in checks:
            print(f"  {'RED ' if not c['ok'] else 'green'} {c['arm']} {c['detail']}")
        if caught:
            print('NEG-ARM: PASS (as seis curas mutadas foram apanhadas)')
            return 1
        print('NEG-ARM: FAIL -- o mutante sobreviveu a um braco')
        return 2

    shell_mod = load(SHELL, 'shell_live')
    sys.path.insert(0, os.path.join(ROOT, 'worker'))
    worker_mod = load(WORKER, 'worker_live')
    checks, ok = judge(shell_mod, worker_mod)
    for c in checks:
        print(f"  {'PASS' if c['ok'] else 'FAIL'} {c['arm']} {c['detail']}")
    print(f"VERDICT: {'PASS' if ok else 'FAIL'} arms={len(checks)} "
          f"fail={sum(1 for c in checks if not c['ok'])}")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
