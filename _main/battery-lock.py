#!/usr/bin/env python
"""battery-lock -- UM run da bateria de cada vez, ou a leitura de quem corre e' lixo.

POR QUE EXISTE (medido 2026-11-05, 06:3x-06:4x). Duas invocacoes de
`_main\\_audit-verify-all.cmd` ficaram vivas ao mesmo tempo (pids 31688 e 56272) e
correram os MESMOS passos sobre os MESMOS ficheiros: `_main\\_audit-verify\\*.log`,
`_main\\_cache\\battery-steps.json` e `_main\\_audit-verify\\_battery-summary.txt`.
O custo foi uma LEITURA ERRADA, e nao hipotetica: li `BATTERY-VERDICT: RED - 9
step(s) failed` num ficheiro escrito as 01:20 por um run antigo e tratei-o como o
veredicto do run que acabara de largar. Nove passos "vermelhos" que eu estava a
cacar eram, em parte, o resumo de outra pessoa. Um resumo que pode descrever outro
run e' pior do que nenhum resumo.

O QUE ESTE FICHEIRO FAZ. Um ficheiro de lock (`_main\\_cache\\battery.lock`) com o
pid de quem o tem. `acquire` recusa com **rc=8** quando o pid la' escrito esta'
VIVO; quando o pid esta' morto o lock e' ESTALE e o run novo toma-o -- um run
interrompido nao pode congelar a bateria para sempre. `release` so' apaga o lock
que e' DELE (mesmo pid), para um run atrasado nao apagar o lock do seguinte.

    python _main\\battery-lock.py acquire    # rc=0 tomei, rc=8 recusado
    python _main\\battery-lock.py release    # rc=0 libertei/nao era meu
    python _main\\battery-lock.py --status   # quem tem, se alguem tem
    python _main\\battery-lock.py --neg-arm  # rc=1 POR DESENHO quando os casos batem
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(HERE, '_cache', 'battery.lock')


def _alive(pid):
    if not pid or pid <= 0:
        return False
    if os.name == 'nt':
        # No Windows nao ha `kill(0)`; `OpenProcess` responde e nao mata nada.
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
        k32.CloseHandle(ctypes.c_void_p(h))
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def holder(path=LOCK):
    """O pid que o lock nomeia, ou 0 quando nao ha' lock legivel."""
    try:
        raw = open(path, encoding='utf-8').read().strip()
    except OSError:
        return 0
    try:
        return int(json.loads(raw).get('pid') or 0)
    except (ValueError, TypeError):
        try:
            return int(raw or 0)
        except ValueError:
            return 0


def acquire(path=LOCK, pid=None, alive=_alive):
    pid = os.getpid() if pid is None else int(pid)
    other = holder(path)
    if other and other != pid and alive(other):
        print('BATTERY-LOCK BUSY pid=%d (um run da bateria esta vivo; '
              'dois runs sobre os mesmos logs produzem um resumo que descreve '
              'outro run)' % other)
        return 8
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.%d' % pid
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump({'pid': pid, 'started': time.strftime('%Y-%m-%dT%H:%M:%S')}, fh)
    os.replace(tmp, path)          # atomico: nunca ha' lock meio escrito
    stale = ' (lock estale de pid %d tomado)' % other if other and other != pid else ''
    print('BATTERY-LOCK TAKEN pid=%d%s' % (pid, stale))
    return 0


def release(path=LOCK, pid=None):
    pid = os.getpid() if pid is None else int(pid)
    other = holder(path)
    if not other:
        print('BATTERY-LOCK NONE')
        return 0
    if other != pid:
        print('BATTERY-LOCK NOT-MINE pid=%d (o lock e de %d)' % (other, pid))
        return 0
    try:
        os.remove(path)
    except OSError:
        pass
    print('BATTERY-LOCK RELEASED pid=%d' % pid)
    return 0


def neg_arm():
    """Os quatro casos, num diretorio temporario. Nenhum deles toca no lock real."""
    import tempfile
    cases = []
    tmp = tempfile.mkdtemp(prefix='batlock-')

    # 1. Sem lock: o primeiro run toma.
    p = os.path.join(tmp, 'a.lock')
    cases.append(('vazio-toma', acquire(p, pid=101, alive=lambda _p: False) == 0
                  and holder(p) == 101))

    # 2. Lock com pid VIVO: o segundo e' recusado com rc=8 e o lock NAO muda.
    r = acquire(p, pid=202, alive=lambda _p: True)
    cases.append(('vivo-recusa', r == 8 and holder(p) == 101))

    # 3. Lock com pid MORTO: e' estale, o run novo toma-o.
    r = acquire(p, pid=303, alive=lambda _p: False)
    cases.append(('morto-toma', r == 0 and holder(p) == 303))

    # 4. `release` de quem nao e' o dono nao apaga o lock alheio.
    r = release(p, pid=404)
    cases.append(('release-alheio', r == 0 and holder(p) == 303))
    r = release(p, pid=303)
    cases.append(('release-dono', r == 0 and holder(p) == 0))

    caught = sum(1 for _n, ok in cases if ok)
    for name, ok in cases:
        print('  %-16s %s' % (name, 'CAUGHT' if ok else 'NOT-CAUGHT'))
    print('NEG-ARM SUMMARY cases=%d caught=%d' % (len(cases), caught))
    print('NEG-ARM: PASS' if caught == len(cases) else 'NEG-ARM: FAIL')
    return 1 if caught == len(cases) else 0


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    if '--status' in argv:
        pid = holder()
        if not pid:
            print('BATTERY-LOCK FREE')
            return 0
        print('BATTERY-LOCK HELD pid=%d alive=%s' % (pid, _alive(pid)))
        return 0
    if 'acquire' in argv:
        return acquire()
    if 'release' in argv:
        return release()
    print(__doc__.strip().splitlines()[-6])
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
