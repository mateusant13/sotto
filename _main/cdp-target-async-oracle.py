#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: Oracle: o `/json/list` do alvo corre FORA do laco de leitura (o id e' lido da memoria) e o rebind de aba morta continua a sair. -- trabalho de LATENCIA pedido pela medicao de 2026-11-08; nao corresponde a nenhum id de `_main/bug-ledger.json`.
"""Oracle: the target id is published off the read path, and the dead tab still cures.

THE MEASUREMENT THIS EXISTS FOR (owner's live instance, pid 42572, 2026-11-08,
`_main/webview-run.log`):

    04:38:04.639 EXTERNAL_CAPTIONS_READ_MS ms=1281.0 phases={'import': 0.0,
        'target': 15.0, 'source': 15.0, 'yt-in': 15.0, 'cdp': 15.0,
        'vid': 1281.0, 'youtube': 1281.0, 'end': 1281.0}
    04:37:03.800 YOUTUBE_TARGET_SLOW ms=1375 vid=sAQTn_qRZPw ttl_s=10   <- same
                                                                       millisecond

The whole 1281 ms landed between the `cdp` mark and the `vid` mark, and the only
work there was `youtube_cdp_source.list_targets()` -- one `/json/list` HTTP GET
to the owner's loaded Chrome that measures 1000-1400 ms. Every ~10 s the caption
read loop produced no frame for a full second.

THE RULE THIS PROVES. The question is paid by the `yt-cdp-target` thread
(`CdpCaptionSource._tid_run`), which publishes `(stamp, video_id)` into
`_tid_cache`; `target_video_id()` reads that memory and does no I/O. The SLOW
signal keeps its name and its fields and names where it was measured
(`src=refresher`), and the dead-tab cure (`YOUTUBE_TARGET_REBOUND`) still fires
in the REAL `_yt_identify`.

ARMS
  A1 NO-BLOCKING  -- `list_targets` faked to sleep 1.2 s; the refresher pays it,
                     and 1000 `target_video_id()` calls stay under 0.05 ms p95.
                     The measurement has a hard deadline, so a mutant that
                     inlines the call FAILS instead of hanging for 20 minutes.
  A2 REBIND       -- `/json/list` returns tab A, then tab B; the refresher
                     publishes B and the real `sotto_webview._yt_identify` logs
                     `YOUTUBE_TARGET_REBOUND was=A now=B why=aba`.
  A3 SLOW-SIGNAL  -- the 1.2 s refresh logs `YOUTUBE_TARGET_SLOW ... ttl_s=10
                     src=refresher` and stretches the cadence to 10 s.
  A4 LIFECYCLE    -- the refresher only starts with `start()`, issues NO request
                     while the source never attached, dies on `stop()`, and a
                     second `start()` does not create a second thread.
  A5 CALLER-THREAD-- after the first publication, no `target_video_id()` call is
                     ever executed by the thread that ran `list_targets`.

Usage:
  py -3 _main/cdp-target-async-oracle.py             # the working tree
  py -3 _main/cdp-target-async-oracle.py --neg-arm   # two mutants in a COPY ->
                                                     # each must turn its arm RED
"""
import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
APP = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(APP, 'sotto_webview.py')
SOURCE = os.path.join(APP, 'youtube_cdp_source.py')

A_VID = 'AAAAAAAAAAA'
B_VID = 'BBBBBBBBBBB'
SLEEP_S = 1.2          # o `/json/list` medido no Chrome carregado do dono
CALLS = 1000
P95_BUDGET_MS = 0.05
TOTAL_BUDGET_S = 0.5   # 1000 leituras de memoria; um mutante inline estoura isto

#: O CORPO QUE FAZ A PERGUNTA SEM FIO. O mutante 1 apaga a LEITURA do cache, e
#: a ancora e' UMA linha, nao o bloco: o bloco inteiro ja' mudou duas vezes por
#: curas alheias (a guarda de attach falhado em 2026-11-05, a linha de idade em
#: 2026-11-09) e cada mudanca deixava o `--neg-arm` em `IMPOSSIVEL: ancora
#: ausente`, ou seja um controlo que nao corre. Com `cached = None` o caminho de
#: memoria desaparece e TODA chamada paga `_tid_refresh()` -- que e' o que o A1
#: (1000 leituras, prazo de 0,5 s, `/json/list` falso de 1,2 s) tem de apanhar.
#: `replace(..., 1)` atinge a PRIMEIRA ocorrencia, que vive no
#: `target_video_id`; a segunda, dentro da espera do `_tid_inline`, nao e' o
#: caminho que o A1 mede.
CACHE_BODY = ("        cached = getattr(self, '_tid_cache', None)\n"
              "        if cached is not None:\n")
INLINE_BODY = ("        return self._tid_refresh()\n"
               "        cached = getattr(self, '_tid_cache', None)\n"
               "        if cached is not None:\n")

#: O mutante 2 apaga o SINAL de lentidao (a cadencia continua a esticar: o que
#: sai do log e' o que a arm A3 julga).
SLOW_LOG = ("            self._log('YOUTUBE_TARGET_SLOW ms=%.0f vid=%s "
            "ttl_s=%.0f '\n"
            "                      'src=%s'\n"
            "                      % (cost_ms, vid or '-', _TID_SLOW_TTL_S,\n"
            "                         'refresher' if probe else 'inline'))\n")
NO_SLOW_LOG = "            pass\n"


def load(path, name):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def tab(vid, title='Algum video - YouTube'):
    # SEM `webSocketDebuggerUrl`: a sonda de "quem toca" nao liga a nada e a
    # escolha cai em `pick_target`, que e' o que estes bracos medem.
    return {'type': 'page', 'url': 'https://www.youtube.com/watch?v=' + vid,
            'title': title}


def p95(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    at = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[at]


def wait_for(predicate, timeout_s, step=0.01):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


def run_arms(cdp, shell_mod):
    """Os bracos, contra o modulo dado. Devolve [(nome, ok, detalhe)]."""
    out = []

    def arm(name, ok, detail):
        out.append((name, bool(ok), detail))
        print('%-14s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))

    # -- A1/A3/A5: o fio paga um `/json/list` de 1.2 s -----------------------
    calls = []          # (thread_name, monotonic)
    logs = []

    def slow_list(port=None, timeout=3.0):
        calls.append((threading.current_thread().name, time.monotonic()))
        time.sleep(SLEEP_S)
        return [tab(A_VID)], 0

    saved_list = cdp.list_targets
    cdp.list_targets = slow_list
    src = cdp.CdpCaptionSource(port=0, log=logs.append)
    src._attached = True          # `_run` marcaria isto depois do attach
    try:
        src.start()
        warmed = wait_for(lambda: int(getattr(src, '_tid_refreshes', 0)) >= 1,
                          4.0 * SLEEP_S)
        arm('A1-WARM', warmed and src.target_video_id() == A_VID,
            'refreshes=%d vid=%r' % (getattr(src, '_tid_refreshes', 0),
                                    src.target_video_id()))
        # A1 -- 1000 chamadas, com um relogio LIMITE: um mutante que volte a
        # fazer a pergunta aqui nao pode ser "medido", tem de ser APANHADO.
        durs = []
        began = time.monotonic()
        idx = 0
        got = []
        breached = False
        while idx < CALLS:
            t0 = time.perf_counter()
            got.append(src.target_video_id())
            durs.append((time.perf_counter() - t0) * 1000.0)
            idx += 1
            if time.monotonic() - began > TOTAL_BUDGET_S + SLEEP_S:
                breached = True
                break
        total = time.monotonic() - began
        p = p95(durs)
        arm('A1-NO-BLOCK',
            (not breached) and total <= TOTAL_BUDGET_S
            and p <= P95_BUDGET_MS and set(got) == {A_VID},
            'calls=%d total=%.3fs p95=%.4fms limite=%.2fms estourou=%s'
            % (len(durs), total, p, P95_BUDGET_MS, breached))
        # A5 -- quem fez o HTTP nunca foi o chamador.
        callers = [n for n, _ in calls
                   if n != cdp._TID_THREAD_NAME]
        arm('A5-CALLER', not callers,
            'pedidos=%d de threads que nao o refrescador: %r'
            % (len(calls), callers[:3]))
        # A3 -- o sinal de lentidao, com o nome de onde foi medido.
        slow = [m for m in logs if m.startswith('YOUTUBE_TARGET_SLOW')]
        line = slow[-1] if slow else ''
        arm('A3-SLOW', bool(slow) and 'src=refresher' in line
            and 'ttl_s=10' in line and 'ms=' in line and ('vid=' + A_VID) in line
            and float(getattr(src, '_tid_ttl', 0) or 0) == cdp._TID_SLOW_TTL_S,
            '%r ttl=%r' % (line[:96], getattr(src, '_tid_ttl', None)))
    finally:
        src.stop()
        cdp.list_targets = saved_list
        if src._thread is not None:
            src._thread.join(timeout=3.0)
        if src._tid_thread is not None:
            src._tid_thread.join(timeout=3.0)

    # -- A4: ciclo de vida -------------------------------------------------
    quiet = []

    def count_list(port=None, timeout=3.0):
        quiet.append((threading.current_thread().name, time.monotonic()))
        raise OSError('arm: porta fechada')

    saved_list = cdp.list_targets
    cdp.list_targets = count_list
    idle = cdp.CdpCaptionSource(port=0, log=lambda _m: None)
    try:
        idle.start()          # `_last_use` fica 0 -> `_run` fica em idle
        first = idle._tid_thread
        idle._tid_start()     # idempotente: nao cria um segundo fio
        time.sleep(0.8)       # sem attach, o refrescador nao pode pedir nada
        from_refresher = [n for n, _ in quiet
                          if n == cdp._TID_THREAD_NAME]
        same_thread = idle._tid_thread is first
        idle.stop()
        died = wait_for(lambda: not idle._tid_thread.is_alive(), 3.0)
        arm('A4-LIFECYCLE',
            bool(first) and same_thread and not from_refresher and died,
            'fio=%r um_so=%s pedidos_sem_attach=%d morreu=%s'
            % (getattr(first, 'name', None), same_thread,
               len(from_refresher), died))
    finally:
        idle.stop()
        cdp.list_targets = saved_list
        if idle._thread is not None:
            idle._thread.join(timeout=3.0)

    # -- A2: o rebind, no `_yt_identify` REAL ------------------------------
    tabs = {'now': [tab(A_VID)]}
    shell_logs = []

    def switch_list(port=None, timeout=3.0):
        return [dict(t) for t in tabs['now']], 0

    saved_list = cdp.list_targets
    cdp.list_targets = switch_list
    src2 = cdp.CdpCaptionSource(port=0, log=lambda _m: None)
    src2._attached = True
    real_log = getattr(shell_mod, 'log', None)
    try:
        shell_mod.log = lambda message, *a, **k: shell_logs.append(str(message))
        src2.start()
        wait_for(lambda: src2._tid_cache is not None, 3.0)
        before = src2.target_video_id()
        # A ABA A' FECHOU: a lista passa a mostrar so' o video B (a cura).
        tabs['now'] = [tab(B_VID)]
        moved = wait_for(lambda: src2.target_video_id() == B_VID, 3.0)
        watcher = shell_mod.ExternalCaptionWatcher(SimpleNamespace())
        watcher._yt_cdp_source = src2
        watcher.yt_video_id = A_VID
        watcher.shell = SimpleNamespace()
        # O REBIND E' DE DUAS LEITURAS DESDE 2026-11-09 (a oscilacao de duas abas
        # apagava a legenda), e a arm testava UMA: a primeira chamada so' ARMA o
        # candidato (`YOUTUBE_TARGET_REBIND_ARMED`) e nao troca nada. A janela de
        # confirmacao e' encurtada aqui para zero para a arm nao pagar o prazo
        # real; a SEGUNDA chamada e' que confirma.
        watcher.YT_REBIND_CONFIRM_S = 0.0
        watcher._yt_identify(1234, object(), object())
        armed = [m for m in shell_logs
                 if m.startswith('YOUTUBE_TARGET_REBIND_ARMED')]
        watcher._yt_identify(1234, object(), object())
        rebound = [m for m in shell_logs
                   if m.startswith('YOUTUBE_TARGET_REBOUND')]
        line = rebound[-1] if rebound else ''
        arm('A2-REBIND',
            before == A_VID and moved and bool(armed) and bool(rebound)
            and ('was=' + A_VID) in line and ('now=' + B_VID) in line
            and 'why=aba' in line and watcher.yt_video_id == B_VID,
            'publicado=%r->%r armed=%d yt_video_id=%r %s'
            % (before, src2.target_video_id(), len(armed),
               getattr(watcher, 'yt_video_id', None), line[:78] or '-'))
    finally:
        cdp.list_targets = saved_list
        if real_log is not None:
            shell_mod.log = real_log
        src2.stop()
        if src2._thread is not None:
            src2._thread.join(timeout=3.0)
        if src2._tid_thread is not None:
            src2._tid_thread.join(timeout=3.0)

    # A4/A5 -- O ORCAMENTO DO LOG DE ESTADO (2026-11-09, DM do watcher 50452).
    #
    # O laco de 8 Hz escrevia 16 linhas/s: `YOUTUBE_CDP_SOURCE` e
    # `YOUTUBE_TARGET` repetiam o MESMO estado 1,18x/s cada e as duas linhas de
    # medida somavam 0,57/s num log de 64,7 MB. As de estado passaram a sair na
    # MUDANCA (batimento de 60 s, `_STATE_HEARTBEAT_S`); as de medida ficaram
    # limitadas por `_YT_RATE_LOG_S`/`_YT_HEALTH_LOG_S` no shell. Estes dois
    # bracos conduzem os METODOS REAIS com um relogio falso: 480 ticks = 60 s de
    # laco a 8 Hz, e contam as linhas que saem.
    class _Clock(object):
        t = 1000.0

        def monotonic(self):
            return self.t

    class _Src(object):
        _reads = 11
        _errors = 0

        def snapshot_age(self):
            return 0.2

        def stats(self):
            return {'reads': 11, 'errors': 0, 'last_error': '', 'note': 'attached'}

    saved_time = shell_mod.time
    saved_log = shell_mod.log
    fake = _Clock()
    lines = []
    try:
        watcher = shell_mod.ExternalCaptionWatcher.__new__(
            shell_mod.ExternalCaptionWatcher)
        shell_mod.time = fake
        shell_mod.log = lines.append
        snap = {'stamp': 1000.0}
        for _ in range(481):   # 60 s de instantes a 8 Hz (0,125 s cada)
            # O RELOGIO ANDA DEPOIS DO TICK, senao o primeiro `t0` nasce
            # adiantado e a sexta janela de 10 s nunca fecha.
            watcher._yt_rate_tick(snap, _Src())
            watcher._yt_health_tick(_Src(), fake.t)
            fake.t += 0.125
    finally:
        shell_mod.time = saved_time
        shell_mod.log = saved_log
    rate = [m for m in lines if m.startswith('YOUTUBE_LOOP_HZ')]
    health = [m for m in lines if m.startswith('YOUTUBE_CDP_HEALTH')]
    # O NUMERO ESPERADO E' UM PIN, NAO UMA DIVISAO PELO PROPRIO CONSTANTE
    # (2026-11-09, MEDIDO). Com `int(60.0 / shell_mod._YT_RATE_LOG_S)` o mutante
    # que devolvia o periodo a 0,125 s mudava TAMBEM a expectativa (esperado=480)
    # e a arm A4 passava com o log a 8 linhas/s: um portao a ler o veredicto da
    # coisa que mede. Resultado medido do braco negativo: `FAIL -- um mutante
    # sobreviveu`, com a A5 a ser a unica a ficar vermelha. Hoje 10 s -> 6 linhas
    # de `YOUTUBE_LOOP_HZ` e 30 s -> 2 de `YOUTUBE_CDP_HEALTH` em 60 s de laco; se
    # a casa mudar o orcamento, estes dois numeros mudam AQUI, a mao.
    want_rate = int(60.0 / 10.0)      # `_YT_RATE_LOG_S`
    want_health = int(60.0 / 30.0)    # `_YT_HEALTH_LOG_S`
    hz_ok = bool(rate) and 'hz=8.0' in rate[-1]
    arm('A4-STATE-RATE', len(rate) == want_rate and hz_ok,
        'YOUTUBE_LOOP_HZ=%d (esperado %d) hz=%r' %
        (len(rate), want_rate, rate[-1].split('hz=')[-1][:5] if rate else '-'))
    per_s = (len(rate) + len(health)) / 60.0
    arm('A5-STATE-BUDGET', len(health) == want_health and per_s <= 0.2,
        'linhas/s=%.3f (alvo <=0.2) rate=%d health=%d (esperado %d)' %
        (per_s, len(rate), len(health), want_health))

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    if not args.neg_arm:
        cdp = load(SOURCE, '_cdp_async_cdp')
        shell_mod = load(SHELL, '_cdp_async_shell')
        rows = run_arms(cdp, shell_mod)
        fails = [r for r in rows if not r[1]]
        print('VERDICT: %s (arms=%d fail=%d)'
              % ('PASS' if not fails else 'FAIL', len(rows), len(fails)))
        return 0 if not fails else 1

    # -- o braco negativo: dois mutantes, cada um numa COPIA ---------------
    original = open(SOURCE, encoding='utf-8', newline='').read()
    mutants = [
        ('inline', CACHE_BODY, INLINE_BODY, 'A1-NO-BLOCK'),
        ('sem-slow-log', SLOW_LOG, NO_SLOW_LOG, 'A3-SLOW'),
    ]
    shell_mod = load(SHELL, '_cdp_async_shell')
    tmpdir = tempfile.mkdtemp(prefix='cdp-target-async-neg-')
    # O MODULO CARREGA O IRMAO PELO CAMINHO (2026-11-08, medido): sem
    # `youtube_window.py` ao lado, a COPIA nem importa -- `FileNotFoundError`
    # no `_load_sibling`, e o braco negativo morria em vez de medir.
    shutil.copy(os.path.join(APP, 'youtube_window.py'),
                os.path.join(tmpdir, 'youtube_window.py'))
    verdict = True
    try:
        for label, old, new, want in mutants:
            if old not in original:
                print('NEG-ARM IMPOSSIVEL: ancora do mutante %r ausente' % label)
                return 2
            path = os.path.join(tmpdir, 'youtube_cdp_source_%s.py'
                                % label.replace('-', '_'))
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(original.replace(old, new, 1))
            print('== mutante %s (%s tem de cair)' % (label, want))
            cdp = load(path, '_cdp_async_mut_%s' % label.replace('-', '_'))
            rows = {r[0]: r for r in run_arms(cdp, shell_mod)}
            hit = rows.get(want)
            red = hit is not None and not hit[1]
            verdict = verdict and red
            print('   %s -> %s' % (want, 'RED (como desenhado)' if red
                                   else 'sobreviveu'))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # O TERCEIRO MUTANTE E' DO SHELL: o periodo de medida volta a ser um tick
    # (`0.125` = 8 linhas/s), que e' o estado medido no log do dono antes da
    # cura. A arm A4 tem de cair; a constante e' restaurada no fim.
    saved_period = shell_mod._YT_RATE_LOG_S
    try:
        shell_mod._YT_RATE_LOG_S = 0.125
        rows = {r[0]: r for r in run_arms(cdp, shell_mod)}
        hit = rows.get('A4-STATE-RATE')
        red = hit is not None and not hit[1]
        verdict = verdict and red
        print('   A4-STATE-RATE -> %s' % ('RED (como desenhado)' if red
                                          else 'sobreviveu'))
    finally:
        shell_mod._YT_RATE_LOG_S = saved_period

    if verdict:
        print('NEG-ARM: PASS (tres mutantes, os tres apanhados)')
        return 1
    print('NEG-ARM: FAIL -- um mutante sobreviveu')
    return 0


if __name__ == '__main__':
    sys.exit(main())
