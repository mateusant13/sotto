#!/usr/bin/env python3
"""ORACLE for the LOAD HONESTY of the two strip-stats gates.

The claim this oracle pins is NOT "the log budget is fine". It is: **a strip-stats
gate that could not MEASURE says so, and a strip-stats gate that DID measure
still fails when the product is broken.**

Measured 2026-10-20, the reason this file exists: the battery went RED because
the BOX was too loaded for the panel to come up. The log-budget gate's
`aggregated` arm never reached `RECEIVER_READY`, wrote zero push lines, and the
ratio -- a division by ~0 -- became `21586300.0x`, printed as
`STRIP-LOG CONTROL FAIL`. The product was fine: the same app on the same box,
idle, reaches `RECEIVER_READY` in 1.98 s. A gate that reports "I could not
measure" as a RED of the product trains its reader to ignore the red, and that
is worse than no gate.

ARMS (in process; the REAL gates, the REAL battery and the REAL machine are
never touched -- the LOADED box is SIMULATED, it is not the owner's box)
    a  os dois bracos chegam a READY e a razao e alta   -> GREEN
    b  um braco NAO chega a READY dentro do prazo       -> SKIP, e o motivo diz
                                                          porque (o prazo, o
                                                          tempo que o braco
                                                          demorou)
    c  os dois bracos chegam a READY mas a razao e BAIXA -> RED  (o mutante
                                                          critico: um gate que
                                                          esconde o defeito)
    d  a maquina carregada e SIMULADA                   -> a decisao nao lanca
                                                          nada e le um log
                                                          sintetico em disco
    e1 o relogio de prontidao le o log CALMO (1,98 s)  -> pronto
    e2 o relogio de prontidao le o log CARREGADO       -> NAO pronto
       (63,58 s, e sem `RECEIVER_READY`)
    f  os DOIS gates usam o modulo comum                -> nenhuma logica da
                                                          decisao duplicada
    g  o prazo e justificado pelos numeros             -> >= 5x o tempo calmo e
                                                          abaixo do carregado

NEGATIVE ARM (executed, not decorative)
    Four BROKEN COPIES of `_main/_strip_stats_load.py`. Each copy is a TEXTUAL
    patch of a unique anchor; an anchor that is missing or ambiguous is
    DECORATIVE and the oracle refuses to count it. The SAME battery runs against
    every mutant, and the mutant must go RED on ITS OWN claim:

      1. "o braco nao chegou a READY" e uma FALHA   -> b tem de ficar RED
      2. "razao baixa com os dois bracos prontos" e   -> c tem de ficar RED
         um SKIP
      3. nunca SKIPa                                 -> b tem de ficar RED
      4. um prazo tao curto que o braco bom tambem    -> a tem de ficar RED
         falha

Usage:
    python _main/_strip-stats-load-oracle.py       # arms + mutants, rc=0 on PASS

It opens no window, no audio device, no network, and it launches NO shell: the
loaded box is a synthetic log written to a temp dir under `I:\\cc-tmp`.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, '_strip_stats_load.py')
LOG_GATE = os.path.join(HERE, '_strip-stats-log-probe.py')
WAVE_GATE = os.path.join(HERE, '_strip-stats-probe.py')

EXIT_PASS = 0
EXIT_FAIL = 1

#: The MEASURED calm timeline (2026-10-20 03:29:44, `I:\cc-tmp\sotto-032942.log`).
CALM_EVENTS = (
    (0.000, 'shell=webview2 pywebview=6.2.1 python=3.11.8 pid=1234'),
    (0.962, 'PANEL_LAZY_GATE_ARMED registered=5 urls=5'),
    (1.950, 'STAGING_LOADED core=yes -> navigating to panel'),
    (1.980, 'RECEIVER_READY captions=0 utterances=0'),
)

#: The MEASURED loaded timeline (2026-10-20 03:20:33 -> 03:21:37,
#: `_strip-stats-log-aggregated-a1-51764-1792477102.log`): the page never went
#: live inside the arm's window.
LOADED_EVENTS = (
    (0.000, 'shell=webview2 pywebview=6.2.1 python=3.11.8 pid=4321'),
    (0.962, 'PANEL_LAZY_GATE_ARMED registered=5 urls=5'),
    (63.580, 'STAGING_SEEN document=stage.html -> bouncing to panel staged=false'),
    (63.580, 'STAGING_LOADED core=yes -> navigating to panel'),
)


def load_module(path, name):
    """Load the module (or a MUTANT of it) from a path."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def fmt_ts(epoch):
    lt = time.localtime(epoch)
    return '%04d-%02d-%02d %02d:%02d:%02d.%03d' % (
        lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec,
        int(round((epoch - int(epoch)) * 1000)) % 1000)


def synth_log(events, base=1700000000.0):
    """A shell-log-shaped text built from (offset_s, message) events."""
    return ''.join('%s sotto: %s\n' % (fmt_ts(base + off), msg)
                   for off, msg in events)


def workdir_root():
    base = os.environ.get('TMPDIR') or r'I:\cc-tmp'
    if not os.path.isdir(base):
        base = os.environ.get('TEMP') or os.environ.get('TMP') or '.'
    path = os.path.join(base, 'strip-stats-load-oracle-%d' % os.getpid())
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    return path


def make_arm(mod, text, tag, push_lines, push_bytes_per_min, delivered,
             waited_s, autostart=('WORKER_AUTOSTART reason=with-worker',),
             shell_alive_at_deadline=True):
    """One synthetic arm: the REAL readiness logic over a synthetic log."""
    arm = dict(mod.arm_readiness(text))
    arm.update({
        'tag': tag,
        'push_lines': push_lines,
        'push_bytes_per_min': push_bytes_per_min,
        'delivered': delivered,
        'waited_s': waited_s,
        'autostart': list(autostart),
        'shell_alive_at_deadline': shell_alive_at_deadline,
    })
    return arm


# ── the battery that runs against the module AND against every mutant ───────

def battery(mod, root, tag):
    rows = []

    def add(ok, name, detail=''):
        rows.append((bool(ok), name, detail))

    calm = synth_log(CALM_EVENTS)
    loaded = synth_log(LOADED_EVENTS)

    # The synthetic logs live ON DISK: the readiness is read from a file, the
    # way the real gate reads the shell's log.
    calm_path = os.path.join(root, 'calm-%s.log' % tag)
    loaded_path = os.path.join(root, 'loaded-%s.log' % tag)
    with open(calm_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(calm)
    with open(loaded_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(loaded)
    calm = mod.read_log(calm_path)
    loaded = mod.read_log(loaded_path)

    # (a) both arms ready, the ratio is HIGH -> GREEN
    per = make_arm(mod, calm, 'per-sample', 480, 254000.0, 480, 2.1)
    agg = make_arm(mod, calm, 'aggregated', 1, 525.0, 480, 2.2)
    verdict = mod.decide([per, agg], mod.budget_checks(per, agg))
    add(verdict['verdict'] == 'GREEN',
        'a os dois bracos chegam a READY e a razao e alta -> GREEN',
        'verdict=%s reason=%s' % (verdict['verdict'], verdict['reason']))

    # (b) ONE arm missed the deadline -> SKIP, and the reason says why
    starved = make_arm(mod, loaded, 'aggregated', 0, 0.0, 0, 30.0)
    per_ok = make_arm(mod, calm, 'per-sample', 159, 84000.0, 159, 4.0)
    verdict = mod.decide([per_ok, starved],
                         mod.budget_checks(per_ok, starved))
    reason = verdict.get('skip_reason') or ''
    add(verdict['verdict'] == 'SKIP'
        and 'aggregated' in reason and '30' in reason,
        'b um braco NAO chega a READY dentro do prazo -> SKIP (e diz porquê)',
        'verdict=%s reason=%s' % (verdict['verdict'], reason))

    # (c) both arms ready, the ratio is LOW -> RED (the defect must show)
    bad_agg = make_arm(mod, calm, 'aggregated', 400, 240000.0, 480, 2.2)
    verdict = mod.decide([per, bad_agg], mod.budget_checks(per, bad_agg))
    add(verdict['verdict'] == 'RED',
        'c os dois bracos chegam a READY mas a razao e BAIXA -> RED',
        'verdict=%s failed=%s' % (verdict['verdict'],
                                  '; '.join(verdict.get('failed') or [])))

    # (h) the shell DIED before the page was live -> RED, never a skip: a
    # shell that is gone did not run slowly, it failed.
    dead = make_arm(mod, loaded, 'aggregated', 0, 0.0, 0, 3.0,
                    shell_alive_at_deadline=False)
    verdict = mod.decide([per_ok, dead], mod.budget_checks(per_ok, dead))
    add(verdict['verdict'] == 'RED',
        'h o braco MORREU antes da pagina ficar viva -> RED (nao e um skip)',
        'verdict=%s skip_reason=%s' % (verdict['verdict'],
                                       verdict.get('skip_reason')))

    # (d) the loaded box is SIMULATED: the decision path launches nothing
    source = read_text(MODULE)
    no_launch = ('subprocess' not in source and 'Popen' not in source
                 and 'os.system' not in source)
    add(no_launch and 'STAGING_SEEN' in loaded,
        'd a maquina carregada e SIMULADA (a decisao nao lanca nada)',
        'module launches nothing=%s | the loaded log is a file on disk=%s'
        % (no_launch, os.path.isfile(loaded_path)))

    # (e1) the readiness clock reads the CALM log
    ready = mod.arm_readiness(calm)
    add(ready['ready'] and ready['ready_s'] is not None
        and abs(ready['ready_s'] - mod.CALM_READY_S) < 0.01,
        'e1 o relogio de prontidao le o log CALMO (1,98 s) -> pronto',
        'ready=%s ready_s=%s deadline=%s'
        % (ready['ready'], ready['ready_s'], ready['deadline_s']))

    # (e2) the readiness clock reads the LOADED log
    late = mod.arm_readiness(loaded)
    add((not late['ready']) and late['ready_s'] is None
        and late['timeline'].get('STAGING_SEEN') is not None
        and abs(late['timeline']['STAGING_SEEN'] - mod.LOADED_STAGE_S) < 0.01,
        'e2 o relogio de prontidao le o log CARREGADO (63,58 s) -> NAO pronto',
        'ready=%s ready_s=%s timeline=%s'
        % (late['ready'], late['ready_s'], late['timeline']))

    # (f) BOTH gates use the shared module: no duplicated decision logic
    for name, path in (('log-budget', LOG_GATE), ('wave', WAVE_GATE)):
        src = read_text(path)
        wired = ('import _strip_stats_load' in src and 'load.decide(' in src
                 and 'def decide(' not in src)
        add(wired, 'f o gate %s usa o modulo comum (nenhuma decisao duplicada)'
            % name,
            'import=%s decide=%s' % ('import _strip_stats_load' in src,
                                     'load.decide(' in src))

    # (g) the deadline is justified by the two measured numbers
    facts = mod.deadline_facts()
    add(bool(facts.get('justified')) and (facts.get('times_calm') or 0) >= 5,
        'g o prazo e justificado (>= 5x o tempo calmo, abaixo do carregado)',
        'deadline=%.0fs calm=%.2fs loaded=%.2fs times_calm=%s below_loaded=%s'
        % (facts['deadline_s'], facts['calm_ready_s'], facts['loaded_stage_s'],
           facts['times_calm'], facts['below_loaded']))

    return rows


# ── the mutants ─────────────────────────────────────────────────────────────

MUTANTS = [
    ("braco-nao-pronto-e-falha",
     ["b um braco NAO chega a READY dentro do prazo -> SKIP (e diz porquê)"],
     "    if skip is not None:\n"
     "        return {'verdict': 'SKIP', 'skip_reason': skip, 'failed': [],\n"
     "                'reason': skip}\n",
     "    if skip is not None:\n"
     "        return {'verdict': 'RED', 'skip_reason': None, 'failed': [skip],\n"
     "                'reason': skip}\n"),
    ("razao-baixa-vira-skip",
     ["c os dois bracos chegam a READY mas a razao e BAIXA -> RED"],
     "    if failed:\n"
     "        return {'verdict': 'RED', 'skip_reason': None, 'failed': failed,\n"
     "                'reason': '; '.join(failed)}\n",
     "    if failed:\n"
     "        return {'verdict': 'SKIP', 'skip_reason': '; '.join(failed),\n"
     "                'failed': failed, 'reason': '; '.join(failed)}\n"),
    ("nunca-skipa",
     ["b um braco NAO chega a READY dentro do prazo -> SKIP (e diz porquê)"],
     "        if arm.get('ready'):\n"
     "            continue\n",
     "        if True:\n"
     "            continue\n"),
    ("prazo-curto demais",
     ["a os dois bracos chegam a READY e a razao e alta -> GREEN"],
     "READY_DEADLINE_S = 30.0\n",
     "READY_DEADLINE_S = 0.5\n"),
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:                                           # noqa: BLE001
        pass

    if not os.path.isfile(MODULE):
        print('RED   module missing: %s' % MODULE)
        return EXIT_FAIL
    with open(MODULE, 'r', encoding='utf-8', newline='') as fh:
        source = fh.read()

    root = workdir_root()
    started = time.monotonic()
    try:
        print('ARMS (a carga e SIMULADA; as portas reais e a maquina real '
              'nao sao tocadas)')
        mod = load_module(MODULE, 'strip_stats_load_live')
        rows = battery(mod, root, 'live')
        for ok, name, detail in rows:
            print('  %s %s%s' % ('GREEN' if ok else 'RED  ', name,
                                 ('  ' + detail) if detail else ''))
        arms_green = sum(1 for ok, _, _ in rows if ok)
        arms_total = len(rows)
        print('\n  %d/%d' % (arms_green, arms_total))

        print('\nNEGATIVE ARM (copias quebradas do modulo tem de ficar RED)')
        caught = 0
        weak = 0
        for idx, (label, expected, old, new) in enumerate(MUTANTS):
            hits = source.count(old)
            if hits != 1:
                print('  RED   mutant %-28s ANCHOR %s -- oracle is stale'
                      % (label, 'MISSING' if hits == 0 else 'AMBIGUOUS'))
                weak += 1
                continue
            path = os.path.join(root, 'mutant_%d.py' % idx)
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(source.replace(old, new, 1))
            try:
                bad = load_module(path, 'strip_stats_load_mut_%d' % idx)
            except Exception as exc:                            # noqa: BLE001
                print('  RED   mutant %-28s DECORATIVO: nao carregou (%s)'
                      % (label, type(exc).__name__))
                weak += 1
                continue
            try:
                mrows = battery(bad, root, 'mut%d' % idx)
            except Exception as exc:                            # noqa: BLE001
                print('  RED   mutant %-28s a bateria rebentou (%s)'
                      % (label, type(exc).__name__))
                weak += 1
                continue
            reds = [name for ok, name, _ in mrows if not ok]
            missing = [e for e in expected if e not in reds]
            if not missing:
                print('  GREEN mutant %-28s caught by: %s'
                      % (label, '; '.join(reds[:3])))
                caught += 1
            elif not reds:
                print('  RED   mutant %-28s SURVIVED -- the gate is blind here'
                      % label)
            else:
                print('  RED   mutant %-28s caught by the WRONG claim (%s); '
                      'its own claim held: %s'
                      % (label, '; '.join(reds[:3]), '; '.join(missing)))
        total = len(MUTANTS)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    took = time.monotonic() - started
    ok = (arms_green == arms_total and caught == total and weak == 0)
    print('\nVERDICT: %s  arms %d/%d  mutants %d/%d  (%.1fs)'
          % ('PASS' if ok else 'FAIL', arms_green, arms_total, caught, total,
             took))
    if weak:
        print('  %d mutante(s) DECORATIVO(S): nao carregaram, logo nao provaram nada.'
              % weak)
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == '__main__':
    sys.exit(main())
