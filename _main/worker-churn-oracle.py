# NO-BUG: O oracle do CHURN DE RECARGA: o shell mata um worker que esta' quieto, e
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
import threading
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

    # -- arm 6: a espera pelo front end NAO cala o batimento ------------------
    # MEDIDO no log do dono (2026-11-05 00:34:59): `BRIDGE_SILENT ms=30000
    # pid=23240` 39 s apos o spawn, com o worker JA' em `model-loaded` -- o
    # `og.Model` leva 2,0-3,2 s sozinho e 35,9 s numa arm, e o `th.join()`
    # inteiro era esse tempo todo sem uma linha de progresso. `progress()` e'
    # chamado pela espera VIVA; o `--neg-arm` muta o laco e este braco cai.
    class _FeFake:
        _join_frontend = worker_mod.StreamAsr._join_frontend

        def __init__(self, th):
            self._fe_started = True
            self._fe_thread = th
            self._fe_error = None

    slow = threading.Thread(target=lambda: time.sleep(2.4), daemon=True)
    slow.start()
    before = worker_mod.PROGRESS['seq']
    _FeFake(slow)._join_frontend()
    after = worker_mod.PROGRESS['seq']
    check('6-frontend-wait-keeps-the-beat',
          after - before >= 2, {'before': before, 'after': after,
                                'phase': worker_mod.PROGRESS['phase']})

    # -- arm 5: a guarda do PARQUE (so' quando nada podia ter sido capturado) --
    pr = worker_mod.park_reason
    guard = {
        'silent-device-parks': pr('silent-device', 'all-flat', 0, False),
        'no-callback-blocks-parks': pr('no-callback-blocks', 'all-flat', 0, False),
        'captions-zero-parks': pr('captions-zero', 'all-flat', 0, False),
        'captions-no-park': pr('silent-device', 'all-flat', 3, False),
        'stop-no-park': pr('silent-device', 'all-flat', 0, True),
        'healthy-no-park': pr('captions-emitted', 'streaming', 0, False),
    }
    check('5-park-only-when-nothing-captured',
          all(guard[k] for k in ('silent-device-parks', 'no-callback-blocks-parks',
                                 'captions-zero-parks'))
          and not guard['captions-no-park'] and not guard['stop-no-park']
          and not guard['healthy-no-park'], guard)

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
            # O RELOGIO TEM DE ANDAR: sem o `sleep` este laco gira a vapor.
            time.sleep(min(t, 0.002))
            self.n += 1
            if self.set_after is not None and self.n >= self.set_after:
                self._set = True
                return True
            return False

    def run_park(probes, should_end=None, set_after=None, probe_count=None):
        """O laco do parque REAL, com uma sonda de fio e um tecto do chamador."""
        seen = []
        stop = FakeStop(set_after=set_after)
        queue = list(probes)
        seq_before = worker_mod.PROGRESS['seq']

        def probe(attempt):
            if probe_count is not None:
                probe_count['n'] += 1
            return queue.pop(0) if queue else {'blocks': 0, 'peak': 0.0, 'captions': 0}

        out = worker_mod.park_session(
            stop, probe, 'silent-device',
            emit=lambda **kw: seen.append(kw), note=lambda msg: None, floor=0.002,
            backoff_base_s=0.01, backoff_max_s=0.02,
            should_end=should_end or (lambda: False))
        return out, seen, stop, worker_mod.PROGRESS['seq'] - seq_before

    # -- arm 6: blocos a aparecer RETOMAM o parque ---------------------------
    # O TECTO DO CHAMADOR E' OBRIGATORIO AQUI: um mutante que nunca retoma
    # giraria para sempre (medido: o `--neg-arm` ficou 300 s a girar na arm 7
    # antes de o tecto existir).
    def _capped(limit):
        box = {'n': 0}

        def _end():
            box['n'] += 1
            return box['n'] > limit
        return _end

    out6, seen6, stop6, seq6 = run_park([
        {'blocks': 60, 'peak': 0.0, 'captions': 0},        # silencio: nao retoma
        {'blocks': 40, 'peak': 0.0625, 'captions': 0},     # sinal: RETOMA
    ], should_end=_capped(25))
    check('6-park-resumes-when-blocks-appear',
          out6['resumed'] and out6['why'] == 'blocks' and out6['attempts'] == 2
          and seen6[0].get('state') == 'worker-parked'
          and any(e.get('state') == 'worker-resumed' for e in seen6)
          and seq6 >= 1,
          {'why': out6['why'], 'attempts': out6['attempts'],
           'states': [e.get('state') for e in seen6], 'seq_moved': seq6})

    # -- arm 7: um dispositivo a APARECER acaba o parque ---------------------
    out7, seen7, stop7, _ = run_park([
        {'blocks': 0, 'peak': 0.0, 'captions': 0, 'census': ('VoiceMeeter Input',)},
        {'blocks': 0, 'peak': 0.0, 'captions': 0,
         'census': ('VoiceMeeter Input', 'Headset')},
    ], should_end=_capped(25))
    check('7-park-resumes-on-census-change',
          out7['resumed'] and out7['why'] == 'census'
          and out7['attempts'] == 2, out7)

    # -- arm 8: o parque NAO TEM TECTO -- o defeito que isto substitui -------
    # A espera anterior (`hold_idle_slot`) fechava aos 600 s e devolvia a sessao
    # a shell, que pagava outra carga. O parque espera enquanto o modelo viver:
    # aqui ele e' conduzido por nove sondas de silencio e NAO fecha sozinho.
    # O tecto conta SONDAGENS, nao chamadas: `_wait` pergunta pelo limite em cada
    # fatia do batimento, e um contador de chamadas daria 2-3 tentativas (medido).
    tries = {'n': 0}
    out8, seen8, stop8, _ = run_park(
        [{'blocks': 60, 'peak': 0.0, 'captions': 0}] * 10,
        should_end=lambda: tries['n'] >= 9, probe_count=tries)
    src8 = io.open(getattr(worker_mod, '__file__', WORKER),
                   encoding='utf-8', newline='').read()
    check('8-park-has-no-time-ceiling',
          out8['attempts'] >= 9 and not out8['resumed']
          and out8['why'] == 'limited'
          and 'IDLE_HOLD_MAX_S' not in src8 and 'hold_idle_slot(' not in src8,
          {'attempts': out8['attempts'], 'why': out8['why'],
           'ceiling_deleted': 'IDLE_HOLD_MAX_S' not in src8})

    # -- arm 9: o parque MANTEM O BATIMENTO A ANDAR --------------------------
    check('9-park-keeps-the-beat-moving',
          worker_mod.PROGRESS['phase'] == 'parked',
          {'phase': worker_mod.PROGRESS['phase']})

    # -- arm 10: o parque esta' LIGADO ao caminho do veredito ----------------
    # O FICHEIRO DO MODULO CARREGADO, nao o do repo: o `--neg-arm` corre sobre uma
    # COPIA mutada, e ler o original deixava o mutante sobreviver (medido).
    src = io.open(getattr(worker_mod, '__file__', WORKER),
                  encoding='utf-8', newline='').read()
    gate = '            _why = park_reason(_verdict, outcome, counters["captions"],'
    i_gate = src.find(gate)
    i_park = src.find('            _parked = park_session(', i_gate + 1) if i_gate >= 0 else -1
    # o `except` que fecha o `try` do run: a chamada tem de estar DENTRO dele
    i_except = src.find('    except KeyboardInterrupt:', i_gate + 1) if i_gate >= 0 else -1
    wired = (i_gate > 0 and i_park > i_gate and 0 < i_except and i_gate < i_except)
    check('10-park-is-wired-into-the-device-verdict-path', wired,
          {'gate_at': i_gate, 'park_at': i_park, 'except_at': i_except})

    ok = all(c['ok'] for c in checks)
    return checks, ok


def mutate_shell(dst):
    """Tira o piso do caminho da saida limpa E a regra do batimento
    (as arms 1 e 3 tem de cair)."""
    src = io.open(SHELL, encoding='utf-8', newline='').read()
    # DUAS aplicacoes do piso, nao uma: o `_restart_delay` (line ~1083) e o
    # `_schedule_restart` (~18477) clamparam o MESMO numero, e a partir de
    # 2026-11-04 a morte por dispositivo passou pelo segundo. Mutar so' a
    # primeira deixava a arm 1 VERDE com o mutante vivo -- medido: `git diff`
    # do merge `first capture fast` e `NEG-ARM FAIL`, braco 1 intacto.
    n_floor = src.count('if floor_ms and delay < floor_ms:')
    assert n_floor >= 1, 'a ancora do piso nao existe'
    out = src.replace('if floor_ms and delay < floor_ms:', 'if False:', n_floor)
    assert out != src, 'a ancora do piso nao existe'
    src, out = out, out.replace("    return 'WORKER_ALIVE' in line", '    return False', 1)
    assert out != src, 'a ancora do is_alive_beat nao existe'
    io.open(dst, 'w', encoding='utf-8', newline='').write(out)


def mutate_worker(dst):
    """Cinco mutacoes no worker: o `progress` parado (arm 4), o parque desligado
    (arm 5), o censo a nunca diferir (arm 7), o portao do parque ARRANCADO do
    caminho do veredito (arm 10) e a espera do front end de volta a um
    `join()` inteiro (arm 6)."""
    src = io.open(WORKER, encoding='utf-8', newline='').read()
    # A ANCORA NAO TRAVA NO FIM DE LINHA (medido 2026-11-05): era
    # `"        PROGRESS['seq'] += 1\r\n"` e o worker esta' em LF, logo o
    # mutante nao se plantava e o `--neg-arm` morria num AssertionError em vez
    # de dizer se o oraculo ve' a regressao.
    out, n_progress = re.subn(r"[ \t]*PROGRESS\['seq'\] \+= 1\r?\n", "", src, count=1)
    assert n_progress == 1, 'a ancora do progress nao existe'
    src, out = out, out.replace("    if verdict in PARK_DEVICE_VERDICTS:", '    if False:', 1)
    assert out != src, 'a ancora do parque nao existe'
    # O portao le' DUAS listas; matar so' uma deixava a arm 5 verde (medido).
    src, out = out, out.replace("    if outcome in PARK_DEVICE_OUTCOMES:", '    if False:', 1)
    assert out != src, 'a ancora do outcome do parque nao existe'
    src, out = out, out.replace(
        "            elif census is not None and census != base_census:",
        '            elif False:', 1)
    assert out != src, 'a ancora do censo nao existe'
    swapped, n = re.subn(
        r"(?m)^            _why = park_reason\(_verdict, outcome, counters\[\"captions\"\],\r?\n"
        r" +stop\.is_set\(\)\)",
        "            _why = None  # mutante: o portao do parque foi arrancado",
        out, count=1)
    assert n == 1, 'a ancora do portao do parque nao existe'
    out = swapped
    # A QUINTA MUTACAO: a espera pelo front end volta a ser um `join()` inteiro,
    # que e' exactamente o defeito medido (35,9 s sem progresso -> `BRIDGE_SILENT
    # ms=30000` -> 1,9 GB recarregados). A arm 6 tem de cair por ELE.
    swapped, n = re.subn(
        r"(?m)^            while th\.is_alive\(\):\r?\n"
        r" +progress\('fe-wait'\)\r?\n"
        r" +th\.join\(2\.0\)",
        "            th.join()", out, count=1)
    assert n == 1, 'a ancora do laco do front end nao existe'
    out = swapped
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
                  and '5-park-only-when-nothing-captured' in red
                  and '7-park-resumes-on-census-change' in red
                  and '10-park-is-wired-into-the-device-verdict-path' in red
                  and '6-frontend-wait-keeps-the-beat' in red)
        print(f'NEG-ARM arms={len(checks)} caidas={red}')
        for c in checks:
            print(f"  {'RED ' if not c['ok'] else 'green'} {c['arm']} {c['detail']}")
        if caught:
            print('NEG-ARM: PASS (as cinco curas mutadas foram apanhadas)')
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
