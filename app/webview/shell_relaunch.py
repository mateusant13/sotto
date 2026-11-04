"""The app relaunches ITSELF when its own source changes -- no owner action, no approval.

WHY THIS FILE EXISTS (the measurement it replaces)
---------------------------------------------------
Showing a code change on the owner's screen used to need one of two things, and he
refused both: a lane launching the app (forbidden: `SOTTO_NEVER_ON_OWNER_SCREEN`) or HIM
closing and reopening it. Medido 2026-10-30, cinco caminhos de largada a partir desta pane
(`medium`, o desktop dele `high`): filho directo nao fala com a taskbar/WebView2;
`explorer.exe <ficheiro>` nao executa (0/3); token emprestado do Explorer nunca executa;
`CreateProcessAsUser` com o token do shell vivo da' `err=5 ACCESS_DENIED` (com braco de
controlo a passar). O UNICO que executa e' a tarefa agendada dele: `schtasks /run /tn
Sotto` produz um processo `high` na sessao dele (provado: pid 32448, `SHELL_CODE_ID` do
disco de hoje, `HOTKEY_REGISTERED`, `TRAY_ICON_ADD ok=true`).

Entao a app usa essa tarefa -- e usa-a sobre SI PROPRIA, porque o pedido do dono
(2026-10-30, verbatim) e' *"vai dar launch sozinho no sotto. e eu nao quero que essa merda
precise de mim aprovando nada"*.

O CONTRATO
----------
* WATCH: os ficheiros que SO' UM RESTART APLICA (`app/webview/*.py`, `app/panel/*`). Um
  worker/ ja' tem hot reload proprio; o painel idem. O que aqui se vigia e' a camada em que
  *"the shell needs a restart"* (palavras do proprio shell, `sotto_webview.py:865`).
* QUANDO: a mudanca tem de estar QUIETA `STABLE_S` segundos (um save e' escrito-e-renomeado,
  nao um evento), a instancia tem de ter `FLOOR_S` de vida (nunca se relanca um shell que
  acabou de nascer e ainda esta' a carregar o modelo), e o shell tem de dizer que esta'
  OCIOSO. As tres recusas sao nomeadas no log.
* TECTO: `CAP_PER_HOUR` relancamentos por hora, contados num ficheiro. Um laco de
  relancamento e' o defeito classico desta ideia, e o tecto e' o que o impede de existir.
* SOM A TOCAR, NAO SE RELANCA (2026-10-30). O dono, verbatim: *"por que a merda do meu
  audio ainda some? arruam caralho"*. Medido em `_main/shell-relaunch.log`: 7 relancamentos
  reais num dia, cada um `kill pid=... confirmado morto` + `schtasks /run` -- e um reinicio
  reabre os dispositivos de audio e mata o worker a meio. `sound_playing` le' o pico dos
  endpoints de renderizacao (so' leitura) e, com som a sair, a mudanca ESPERA: ela nao se
  perde, aplica-se no primeiro `tick` depois de o som parar.
* A RECUSA DO TECTO FALA UMA VEZ POR MINUTO, nao a cada sonda: medido, 14 linhas
  `SHELL_RELAUNCH_REFUSED` em 67 s de relogio (08:16:27..08:17:33).
* SE A TAREFA FALHAR, NAO SE SAI. Um `os._exit` depois de uma ordem que falhou deixava o
  dono sem app -- o pior resultado possivel. Falha => log, backoff, continua vivo.
* O watcher NUNCA mata a app: uma excepcao no watcher e' um relatorio de bug, nao a morte
  da app (a mesma regra do `hot_reload.py`).

RUN IT STANDALONE -- `python shell_relaunch.py --selftest`
Exercita deteccao, debounce, piso, tecto, ociosidade e o caminho de falha contra um
directorio temporario. Nao toca na tarefa agendada: o `runner` e' injectado.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

#: Segundos de silencio depois da ULTIMA escrita, por ficheiro. Um save de editor e' um
#: burst (write-temp, rename), e agir no primeiro evento relancaria a app a meio do save.
STABLE_S = 4.0

#: Piso de vida da instancia. Abaixo disto, uma mudanca no disco espera: o arranque
#: carrega o modelo e um relancamento aqui seria churn (a doenca que o `restart-30s`
#: gate do shell ja' documenta).
FLOOR_S = 120.0

#: Tecto por hora. E' o que impede um laco (ficheiro tocado por um relancamento, etc.).
CAP_PER_HOUR = 3

#: Intervalo da sonda. 5 s e' barato (um `stat` por ficheiro) e um relancamento nao tem
#: premio em ser instantaneo.
POLL_S = 5.0

#: Depois de a tarefa FALHAR, quanto tempo a app espera antes de tentar outra vez.
BACKOFF_S = 600.0

#: A recusa do tecto e' um ESTADO, nao um evento: uma linha por minuto basta, e medido
#: foram 14 em 67 s antes desta taxa existir.
CAP_LOG_EVERY_S = 60.0

#: O que so' um restart aplica. Directorios relativos a raiz do repo.
WATCH_DIRS = ('app/webview', 'app/panel')
WATCH_SUFFIXES = ('.py', '.js', '.html')

#: A tarefa agendada que executa em nome do dono, na sessao dele (ver o docstring).
TASK = 'SottoRelaunch'

COUNTER_REL = os.path.join('_main', 'shell-relaunch.json')


def fingerprint(root, dirs=WATCH_DIRS, suffixes=WATCH_SUFFIXES):
    """{relpath: (size, mtime_ns)} -- barato, e suficiente para 'mudou'."""
    out = {}
    for rel_dir in dirs:
        base = os.path.join(root, rel_dir)
        try:
            names = os.listdir(base)
        except OSError:
            continue
        for name in names:
            if not name.endswith(suffixes):
                continue
            path = os.path.join(base, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            out[os.path.join(rel_dir, name).replace('\\', '/')] = (st.st_size, st.st_mtime_ns)
    return out


def changed_files(before, after):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def _read_counter(path):
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    stamps = [t for t in data.get('relaunches', []) if isinstance(t, (int, float))]
    return {'relaunches': stamps}


def _write_counter(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
    except OSError:
        pass


def within_cap(stamps, now, per_hour=CAP_PER_HOUR):
    recent = [t for t in stamps if now - t < 3600.0]
    return len(recent) < per_hour, recent


class Relauncher:
    """O vigia. Uma instancia por processo; `arm()` e' o unico construtor que a app usa."""

    def __init__(self, root, ready, log=None, runner=None, exit_fn=None,
                 counter_path=None, clock=time.time, sleep_s=POLL_S,
                 record_path=None, sound_playing=None):
        self.root = root
        self.ready = ready
        self.log = log or (lambda _msg: None)
        self.runner = runner or _run_task
        self.exit_fn = exit_fn or (lambda code: os._exit(code))
        self.counter_path = counter_path or os.path.join(root, COUNTER_REL)
        self.record_path = record_path or os.path.join(root, '_main', 'shell-relaunch.log')
        self.clock = clock
        self.sleep_s = sleep_s
        self.started = clock()
        # `seen` e' a assinatura que JA' VIMOS, actualizada a cada volta. Sem isto o
        # primeiro `tick` depois da mudanca repete a mesma diferenca, re-arma o relogio
        # do debounce e o relancamento NUNCA acontece (defeito apanhado pelo selftest).
        self.seen = fingerprint(root)
        self.pending = {}           # relpath -> instante da ultima escrita NOVA vista
        self.backoff_until = 0.0
        self.fired = 0
        #: Som a sair do PC: a mudanca espera (ver o docstring). `None` = sem sonda.
        self.sound_playing = sound_playing
        self._deferral_logged = False
        self._last_cap_log = 0.0
        self._stop = threading.Event()
        self._thread = None

    def record(self, msg):
        """A linha de registo DURAVEL: escrita e sincronizada antes de qualquer `exit`.

        O `log` do shell passa por uma fila; `os._exit` nao a drena (medido). A decisao
        de se sentar de novo tem de sobreviver a isso, ou o dono fica com uma app que
        reiniciou e nenhum registo de por que.
        """
        line = '%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
        try:
            os.makedirs(os.path.dirname(self.record_path), exist_ok=True)
            with open(self.record_path, 'a', encoding='utf-8') as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError:
            pass
        try:
            self.log(msg)
        except Exception:                             # noqa: BLE001
            pass

    # -- decisao, separada do laco para ser testavel sem relogio real -------
    def tick(self, now=None):
        """Uma volta. Devolve a accao tomada: 'idle' | 'changed' | 'wait' | 'fire'."""
        now = self.clock() if now is None else now
        after = fingerprint(self.root)
        for name in changed_files(self.seen, after):
            self.pending[name] = now
        self.seen = after
        if not self.pending:
            return 'idle'
        quiet_for = now - max(self.pending.values())
        if quiet_for < STABLE_S:
            return 'wait'
        if now < self.backoff_until:
            return 'wait'
        if now - self.started < FLOOR_S:
            return 'wait'
        allowed, recent = within_cap(_read_counter(self.counter_path)['relaunches'], now)
        if not allowed:
            if now - self._last_cap_log >= CAP_LOG_EVERY_S:
                self._last_cap_log = now
                self.record('SHELL_RELAUNCH_REFUSED reason=cap per_hour=%d recent=%d'
                            % (CAP_PER_HOUR, len(recent)))
            return 'wait'
        # O SOM VEM ANTES DA OCIOSIDADE: um reinicio com musica a tocar e' um corte
        # audivel, mesmo com o semaforo das legendas desligado.
        sounding = False
        if self.sound_playing is not None:
            try:
                sounding = bool(self.sound_playing())
            except Exception as exc:                  # noqa: BLE001 - nunca mata a app
                self.record('SHELL_RELAUNCH_SOUND_FAILED error=%r (a tratar como mudo)'
                            % (exc,))
                sounding = False
        if sounding:
            if not self._deferral_logged:
                self._deferral_logged = True
                self.record('SHELL_RELAUNCH_DEFERRED reason=audio '
                            'files=%s why=do-not-cut-the-owner-audio'
                            % ','.join(sorted(self.pending)))
            return 'wait'
        self._deferral_logged = False
        try:
            busy = not self.ready()
        except Exception as exc:                      # noqa: BLE001 - nunca mata a app
            self.record('SHELL_RELAUNCH_READY_FAILED error=%r (a tratar como ocupado)' % (exc,))
            busy = True
        if busy:
            return 'wait'
        names = ','.join(sorted(self.pending))
        ok, detail = self.runner()
        if not ok:
            self.backoff_until = now + BACKOFF_S
            self.pending.clear()
            self.record('SHELL_RELAUNCH_FAILED files=%s detail=%s backoff_s=%.0f'
                        % (names, detail, BACKOFF_S))
            return 'wait'
        _write_counter(self.counter_path,
                       {'relaunches': (recent + [now])[-CAP_PER_HOUR:]})
        self.fired += 1
        self.record('SHELL_RELAUNCH files=%s detail=%s' % (names, detail))
        self.pending.clear()
        self.exit_fn(0)
        return 'fire'

    def run_forever(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:                  # noqa: BLE001 - ver o docstring
                self.record('SHELL_RELAUNCH_WATCHER_ERROR error=%r' % (exc,))
            self._stop.wait(self.sleep_s)

    def start(self):
        self._thread = threading.Thread(target=self.run_forever,
                                        name='sotto-shell-relaunch', daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop.set()


def _run_task(task=TASK):
    """Dispara a tarefa agendada do dono. (ok, detalhe)."""
    try:
        result = subprocess.run(['schtasks', '/run', '/tn', task], capture_output=True,
                                close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except OSError as exc:
        return False, repr(exc)
    return result.returncode == 0, 'schtasks rc=%d' % result.returncode


def arm(shell, log, task=TASK, sound_playing=None):
    """Arma o vigia no shell vivo. `shell` so' tem de ter `_caption_wanted` (ou nada).

    Ready = ele NAO esta' a ver legendas E nao ha' som a sair do PC. Nunca se mata uma
    transcricao -- nem o audio do dono -- a meio por causa de uma mudanca de ficheiro; a
    mudanca espera, e o nome do ficheiro fica no log.

    `sound_playing` e' a sonda (ver `audio_playing.playing`). Injectavel para o oraculo
    poder exercitar a recusa sem depender do que ele tem a tocar; `None` deixa o vigia
    sem guarda de som (o comportamento anterior, nomeado no log).
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def ready():
        return not bool(getattr(shell, '_caption_wanted', False))

    if sound_playing is None:
        try:
            import audio_playing
            sound_playing = audio_playing.playing
        except Exception as exc:                      # noqa: BLE001 - nunca custa o arranque
            log('SHELL_RELAUNCH_SOUND_PROBE_OFF error=%r' % (exc,))
            sound_playing = None

    relauncher = Relauncher(root, ready, log=log,
                            runner=lambda: _run_task(task),
                            sound_playing=sound_playing)
    relauncher.start()
    log('SHELL_RELAUNCH_ARMED task=%s watched=%s floor_s=%.0f cap_per_hour=%d '
        'stable_s=%.0f sound_gate=%s'
        % (task, ','.join(WATCH_DIRS), FLOOR_S, CAP_PER_HOUR, STABLE_S,
           'on' if sound_playing is not None else 'off'))
    return relauncher


# --------------------------------------------------------------------- selftest

def _selftest():
    """Exercita as seis recusas e o disparo, num directorio temporario."""
    root = tempfile.mkdtemp(prefix='sotto-relaunch-')
    os.makedirs(os.path.join(root, 'app', 'webview'), exist_ok=True)
    os.makedirs(os.path.join(root, 'app', 'panel'), exist_ok=True)
    target = os.path.join(root, 'app', 'webview', 'sotto_webview.py')
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write('x = 1\n')
    now = [1000.0]
    calls = []
    exits = []
    armed = [True]

    def runner():
        calls.append(now[0])
        return armed[0], 'stub'

    r = Relauncher(root, lambda: True, log=lambda m: None, runner=runner,
                   exit_fn=lambda code: exits.append((now[0], code)),
                   clock=lambda: now[0], counter_path=os.path.join(root, 'n.json'))
    fails = []

    def arm(msg, cond):
        if not cond:
            fails.append(msg)

    arm('nenhuma mudanca -> idle', r.tick() == 'idle')
    # 1. deteccao + debounce
    now[0] = 1500.0                                   # piso cumprido
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write('x = 2\n')
    os.utime(target, (1, 1))
    arm('mudanca detectada -> wait (quieto < STABLE_S)', r.tick() == 'wait')
    arm('ainda nao disparou', not calls)
    now[0] += STABLE_S + 0.1
    arm('quieto -> fire', r.tick() == 'fire')
    arm('disparou uma vez', len(calls) == 1)
    arm('saiu com 0', exits == [(now[0], 0)])
    arm('contador gravado', len(_read_counter(os.path.join(root, 'n.json'))['relaunches']) == 1)
    # 2. piso: nova instancia, mudanca antes do piso
    exits.clear()
    r2 = Relauncher(root, lambda: True, runner=runner, exit_fn=lambda c: exits.append(c),
                    clock=lambda: now[0], counter_path=os.path.join(root, 'n2.json'))
    now[0] += 1.0
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write('x = 3\n')
    os.utime(target, (2, 2))
    r2.tick()
    now[0] += STABLE_S + 0.1
    arm('piso recusa antes de FLOOR_S', r2.tick() == 'wait' and not exits)
    # 3. ociosidade
    idle = [False]        # ready() responde "e' seguro relancar AGORA?"
    r3 = Relauncher(root, lambda: idle[0], runner=runner, exit_fn=lambda c: exits.append(c),
                    clock=lambda: now[0], counter_path=os.path.join(root, 'n3.json'))
    r3.started = now[0] - FLOOR_S - 1
    r3.seen = fingerprint(root)
    now[0] += 1.0
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write('x = 4\n')
    os.utime(target, (3, 3))
    r3.tick()
    now[0] += STABLE_S + 0.1
    arm('ocupado recusa', r3.tick() == 'wait' and not exits)
    idle[0] = True
    arm('livre -> dispara', r3.tick() == 'fire' and len(exits) == 1)
    # 4. tecto
    calls.clear()
    exits.clear()
    counter = os.path.join(root, 'n4.json')
    _write_counter(counter, {'relaunches': [now[0], now[0], now[0]]})
    r4 = Relauncher(root, lambda: True, runner=runner, exit_fn=lambda c: exits.append(c),
                    clock=lambda: now[0], counter_path=counter)
    r4.started = now[0] - FLOOR_S - 1
    r4.seen = fingerprint(root)
    now[0] += 1.0
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write('x = 5\n')
    os.utime(target, (4, 4))
    r4.tick()
    now[0] += STABLE_S + 0.1
    arm('tecto recusa o quarto', r4.tick() == 'wait' and not calls and not exits)
    # 5. falha da tarefa: NAO sai, entra em backoff
    armed[0] = False
    calls.clear()
    exits.clear()
    r5 = Relauncher(root, lambda: True, runner=runner, exit_fn=lambda c: exits.append(c),
                    clock=lambda: now[0], counter_path=os.path.join(root, 'n5.json'))
    r5.started = now[0] - FLOOR_S - 1
    r5.seen = fingerprint(root)
    now[0] += 1.0
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write('x = 6\n')
    os.utime(target, (5, 5))
    r5.tick()
    now[0] += STABLE_S + 0.1
    arm('falha da tarefa nao provoca exit', r5.tick() == 'wait' and not exits)
    arm('falha entra em backoff', r5.backoff_until > now[0])
    arm('falha tentou a tarefa uma vez', len(calls) == 1)
    # 6. o registo do disparo sobrevive ao `os._exit` (o log do shell passa por uma
    #    fila que o exit nao drena: medido 2026-10-30, a linha do disparo perdeu-se)
    record = os.path.join(root, 'durable.log')
    armed[0] = True
    exits.clear()
    r6 = Relauncher(root, lambda: True, runner=runner, exit_fn=lambda c: exits.append(c),
                    clock=lambda: now[0], counter_path=os.path.join(root, 'n6.json'),
                    record_path=record)
    r6.started = now[0] - FLOOR_S - 1
    r6.seen = fingerprint(root)
    now[0] += 1.0
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write('x = 7\n')
    os.utime(target, (6, 6))
    r6.tick()
    now[0] += STABLE_S + 0.1
    r6.tick()
    body = open(record, encoding='utf-8').read() if os.path.exists(record) else ''
    arm('o registo do disparo e escrito ANTES do exit', 'SHELL_RELAUNCH files=' in body)

    # 7. SOM A TOCAR -- a recusa que o dono pediu (2026-10-30, verbatim: "por que a
    #    merda do meu audio ainda some? arruam caralho"). Um reinicio com som a sair
    #    reabre os dispositivos e mata o worker a meio: a mudanca ESPERA, e aplica-se
    #    no primeiro tick depois de o som parar. Os dois bracos andam AOS PARES: sem o
    #    segundo, um `return 'wait'` incondicional passaria o primeiro.
    sound = [True]
    exits.clear()
    calls.clear()
    record7 = os.path.join(root, 'audio.log')
    ready7 = [True]
    r7 = Relauncher(root, lambda: ready7[0], runner=runner,
                    exit_fn=lambda c: exits.append(c),
                    clock=lambda: now[0], counter_path=os.path.join(root, 'n7.json'),
                    record_path=record7, sound_playing=lambda: sound[0])
    r7.started = now[0] - FLOOR_S - 1
    r7.seen = fingerprint(root)
    now[0] += 1.0
    with open(target, 'w', encoding='utf-8') as fh:
        fh.write('x = 8\n')
    os.utime(target, (7, 7))
    r7.tick()
    now[0] += STABLE_S + 0.1
    arm('som a tocar recusa o reinicio', r7.tick() == 'wait' and not exits and not calls)
    r7.tick()
    body7 = open(record7, encoding='utf-8').read() if os.path.exists(record7) else ''
    arm('a recusa por som fica no registo DURAVEL',
        'SHELL_RELAUNCH_DEFERRED reason=audio' in body7)
    arm('a recusa por som fala UMA vez, nao a cada sonda',
        body7.count('SHELL_RELAUNCH_DEFERRED reason=audio') == 1)
    sound[0] = False
    arm('o som parou -> a mudanca esperada APLICA-SE',
        r7.tick() == 'fire' and len(exits) == 1)

    # 7. o runner por omissao e' a TAREFA, nunca um python directo
    # LER O CODIGO, NAO O COMENTARIO: o nome `CreateProcessAsUser` aparece no docstring
    # (e na medicao que justifica este ficheiro); o que o braco fixa e' o que a FUNCAO do
    # disparo faz. Um braco que le' texto condena quem documenta.
    import ast
    tree = ast.parse(open(os.path.abspath(__file__), 'r', encoding='utf-8').read())
    body = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_run_task':
            body = ast.get_source_segment(open(os.path.abspath(__file__), 'r',
                                               encoding='utf-8').read(), node) or ''
    arm('a funcao do disparo existe', bool(body))
    arm('o disparo e schtasks /run', "schtasks" in (body or '')
        and "'/run'" in (body or ''))
    arm('o disparo nao cria processos a mao',
        not any(tok in (body or '') for tok in ('CreateProcess', 'Popen', 'os.execv')))
    shutil.rmtree(root, ignore_errors=True)
    for msg in fails:
        print('FAIL %s' % msg)
    print('SHELL-RELAUNCH SELFTEST %s (%d falha(s))'
          % ('PASS' if not fails else 'FAIL', len(fails)))
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    ap.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
