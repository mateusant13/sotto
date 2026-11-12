#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: Oracle de LATENCIA do caminho CDP da legenda -- o tick le' memoria, a
# sonda tem orcamento de relogio, e a idade do id publicado sai no log.
"""Oracle: the caption tick never pays the CDP transport, and the probe is bounded.

MEDIDO em 2026-11-09 contra o Chrome VIVO do dono (read-only, `/json/list` only):

    raw-tcp-connect   median=0.41 ms  max=10.59 ms
    urllib /json/list median=3.24 ms  max=12.41 ms  bytes=25798
    probe_tabs        ~1006 ms        <-- a aba E606035C nao responde a
                                          `Runtime.evaluate` nem em 6,0 s; o
                                          prazo de 1,0 s dela era o custo
    YOUTUBE_TARGET_SLOW ms=1015 ... src=refresher   (11 em 11 s)

O que este oraculo julga, com um transporte FALSO de 1 s (sem Chrome):

  L1 tick-nao-paga   1000 chamadas a `snapshot()` + `target_video_id()` nao
                     podem custar 1 s; p95 < `L1_BUDGET_MS` e o valor e' o do
                     cache.
  L2 idade-nomeada   um id que o refrescador devia ter substituido e nao
                     substituiu sai como `YOUTUBE_TARGET_STALE age_ms=...`.
  L3 sonda-orcada    uma aba congelada (recv de 5 s) nao segura a sonda alem de
                     `PROBE_BUDGET_S` + folga; a aba viva continua a decidir, e
                     `YOUTUBE_PROBE_BUDGET` diz quantas foram abandonadas.
  L4 frio-nao-prende sem ligacao e sem cache, `target_video_id()` responde ''
                     dentro de `_TID_INLINE_WAIT_S` + folga, e a pergunta corre
                     no fio `yt-cdp-inline` -- NUNCA no fio do chamador.

`--neg-arm` muta uma COPIA do modulo (nunca o ficheiro): um `return` inline no
`target_video_id`, um `join()` sem prazo no `probe_tabs` e a linha de idade
apagada. Os tres mutantes tem de deixar o oraculo VERMELHO.

Uso: python _main/youtube-cdp-latency-oracle.py [--neg-arm]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
APP = os.path.join(ROOT, 'app', 'webview')
SOURCE = os.path.join(APP, 'youtube_cdp_source.py')

A_VID = 'AAAAAAAAAAA'
G_VID = 'GGGGGGGGGGG'
SLEEP_S = 1.0            # o transporte falso: 1 s por pergunta
CALLS = 1000
L1_BUDGET_MS = 5.0       # p95 de 1000 chamadas do tick, com transporte de 1 s

#: Ancoras dos mutantes (cada uma tem de existir UMA vez no ficheiro).
#: A FONTE QUE NUNCA ARRANCOU responde no fio do chamador (barata, sem sonda)
#: e e' a UNICA chamada sincrona que sobra; o mutante troca o fio do ticket
#: (`_tid_inline`, com tecto) pela pergunta inteira (`_tid_refresh`).
ANCHOR_INLINE = "            return self._tid_inline()\n"
MUT_INLINE = "            return self._tid_refresh()\n"
# A ANCORA ACOMPANHA A POPULACAO FATIADA (2026-11-12): o laco passou a unir
# `threads[first:]` e ganhou o ramo `deadline is None` por cima, logo a ancora
# antiga (`for th in threads:`) aparecia 0 vezes e o `--neg-arm` respondia
# `NEG-ARM IMPOSSIVEL` com rc=2 -- um controlo que nao corre nao e' um controlo.
# O mutante arranca SO' o orcamento do ramo com prazo (o outro junta sem prazo
# por desenho), que e' exactamente a metade que a arm L3 mede.
ANCHOR_BUDGET = "        else:\n" \
                "            for th in threads[first:]:\n" \
                "                th.join(max(0.0, deadline - time.monotonic()))\n"
MUT_BUDGET = "        else:\n" \
             "            for th in threads[first:]:\n" \
             "                th.join()\n"
ANCHOR_STALE = "            self._tid_stale_note(now - cached[0])\n"
MUT_STALE = "            pass\n"


def load(path, name):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def tab(vid):
    # SEM `webSocketDebuggerUrl`: a sonda de WebSocket nao liga a nada e a
    # escolha cai em `pick_target`, que e' o que estes bracos medem.
    return {'type': 'page', 'url': 'https://www.youtube.com/watch?v=' + vid,
            'title': 'video - YouTube'}


def p95(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def wait_for(predicate, timeout_s, step=0.01):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


class _GoodConn(object):
    """Uma resposta CDP honesta: devolve o payload de `PLAYING_JS` no id pedido."""

    def __init__(self):
        self._id = 1

    def settimeout(self, _t):
        pass

    def send(self, payload):
        try:
            self._id = int(json.loads(payload).get("id") or 1)
        except (TypeError, ValueError):
            self._id = 1

    def recv(self):
        value = json.dumps({"videoId": G_VID, "t": 3.0, "paused": False})
        return json.dumps({"id": self._id,
                           "result": {"result": {"value": value}}})

    def close(self):
        pass


class _FrozenConn(object):
    """Um renderer CONGELADO: `Runtime.evaluate` nunca responde."""

    def __init__(self, sleep_s):
        self._sleep_s = sleep_s

    def settimeout(self, _t):
        pass

    def send(self, _payload):
        pass

    def recv(self):
        time.sleep(self._sleep_s)
        raise TimeoutError('frozen')

    def close(self):
        pass


def _warm(mod, logs, sleep_s=SLEEP_S):
    """Uma fonte ligada com um transporte de `sleep_s`; espera a publicacao."""
    src = mod.CdpCaptionSource(port=0, log=logs.append)
    src._attached = True
    src._connect = lambda _ws: None      # `_run` nao liga a nada de verdade
    try:
        src.start()
    except Exception:                     # noqa: BLE001
        pass
    ok = wait_for(lambda: int(getattr(src, '_tid_refreshes', 0)) >= 1,
                  4.0 * sleep_s + 1.0)
    return src, ok


def run_arms(mod):
    out = []
    logs = []
    seen_threads = []

    def arm(name, ok, detail):
        out.append((name, bool(ok), detail))
        print('%-16s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))

    def slow_list(port=None, timeout=3.0):
        seen_threads.append(threading.current_thread().name)
        time.sleep(SLEEP_S)
        return [tab(A_VID)], 0

    # -- L1/L2: o tick nao paga o transporte, e a idade sai no log ----------
    src = None
    old_list = mod.list_targets
    mod.list_targets = slow_list
    try:
        src, warmed = _warm(mod, logs)
        # O REGIME QUE INTERESSA (2026-11-09): a fonte perdeu a ligacao depois
        # de ter publicado -- e' o ciclo `slow-dead` medido no log do dono. O
        # cache tem de continuar a responder, e o refrescador nao volta a
        # publicar (sem `_attached` ele fica inerte por desenho).
        src._attached = False
        src._tid_ttl = mod._TID_TTL_S     # a cadencia rapida, para a idade
        durs = []
        got = []
        for _ in range(CALLS):
            t0 = time.perf_counter()
            got.append(src.target_video_id())
            snap = src.snapshot(max_age=0.6)
            durs.append((time.perf_counter() - t0) * 1000.0)
        p = p95(durs)
        arm('L1-TICK-FREE',
            warmed and p <= L1_BUDGET_MS and set(got) == {A_VID}
            and snap is None,
            'warm=%s calls=%d p95=%.4fms limite=%.2fms vid=%r'
            % (warmed, CALLS, p, L1_BUDGET_MS,
               sorted(set(got))[:2]))
        # L2 -- a idade do id, depois de DUAS cadencias sem publicacao.
        time.sleep(mod._TID_TTL_S * 2.0 + 0.15)
        src.target_video_id()
        stale = [m for m in logs if m.startswith('YOUTUBE_TARGET_STALE')]
        line = stale[-1] if stale else ''
        arm('L2-STALE-LOG',
            bool(line) and 'age_ms=' in line and 'ttl_s=' in line
            and 'attached=False' in line and 'refreshes=' in line,
            '%r' % (line[:110] or '-'))
    finally:
        mod.list_targets = old_list
        if src is not None:
            src.stop()
            for th in (getattr(src, '_thread', None),
                       getattr(src, '_tid_thread', None)):
                if th is not None:
                    th.join(timeout=3.0)

    # -- L3: uma aba CONGELADA nao segura a sonda alem do orcamento ---------
    # COM `webSocketDebuggerUrl` (o unico campo que `_probe_one` le' antes de
    # ligar): sem ele a sonda nem chega ao transporte falso.
    tabs = [dict(tab(G_VID), webSocketDebuggerUrl='ws://good'),
            dict(tab(A_VID), webSocketDebuggerUrl='ws://frozen')]

    def frozen_connect(url, timeout=None):
        if 'frozen' in str(url):
            return _FrozenConn(5.0)
        return _GoodConn()

    logs3 = []
    t0 = time.monotonic()
    probes = mod.probe_tabs(tabs, connect=frozen_connect,
                            timeout=mod.PROBE_TIMEOUT_S, gap_s=0.0,
                            budget_s=mod.PROBE_BUDGET_S, log=logs3.append)
    elapsed = time.monotonic() - t0
    vids = [str(p.get('videoId') or '') for p in probes]
    budget = [m for m in logs3 if m.startswith('YOUTUBE_PROBE_BUDGET')]
    line = budget[-1] if budget else ''
    # O NUMERO QUE IMPORTA E' 5000 ms, NAO 500: a aba congelada dorme 5 s no
    # `recv`; o orcamento de 500 ms pode derrapar no `join` sob carga (medido
    # 531-641 ms isolado, 844 ms com a maquina a ferver), mas nunca ate' aos
    # 5 s. O que o braco julga e' que a sonda VOLTOU e que a aba VIVA decidiu.
    arm('L3-PROBE-BUDGET',
        elapsed < 2.0 and vids == [G_VID] and 'abandoned=1' in line,
        'ms=%.0f budget_ms=%.0f frozen_s=5.0 probes=%r %r'
        % (elapsed * 1000.0, mod.PROBE_BUDGET_S * 1000.0, vids,
           line[:78] or '-'))

    # -- L4: sem ligacao e sem cache, a pergunta nao corre no fio do laco ---
    ran_on = []

    def hanging_list(port=None, timeout=3.0):
        ran_on.append(threading.current_thread().name)
        time.sleep(SLEEP_S)
        return [tab(A_VID)], 0

    old_list = mod.list_targets
    mod.list_targets = hanging_list
    cold = None
    try:
        cold = mod.CdpCaptionSource(port=0, log=lambda _m: None)
        # O FIO JA' EXISTE QUANDO A FONTE ARRANCA (o app chama `start()` no
        # arranque): `Thread.start()` sozinho custa 240-340 ms sob carga, e
        # medi-lo aqui seria medir o escalonador, nao o caminho da pergunta.
        cold.start()
        time.sleep(0.05)
        # TRES AMOSTRAS, A MEDIANA: um unico numero nesta maquina e' o
        # escalonador a falar (medido 109 ms isolado, 782 ms com os outros
        # agentes a compilar). O que se exige e' a MEDIANA dentro do prazo e
        # NENHUMA amostra a chegar ao transporte (1 s).
        samples = []
        mine = threading.current_thread().name
        for _ in range(3):
            cold._tid_cache = None
            cold._tid_inline_at = 0.0
            cold._tid_inline_job = None
            t0 = time.monotonic()
            vid = cold.target_video_id()
            samples.append((time.monotonic() - t0) * 1000.0)
        samples.sort()
        med = samples[len(samples) // 2]
        arm('L4-COLD-BOUND',
            vid == '' and med <= (mod._TID_INLINE_WAIT_S + 0.15) * 1000.0
            and samples[-1] < SLEEP_S * 1000.0
            and mine not in ran_on
            and (not ran_on or ran_on[0] == 'yt-cdp-target'),
            'vid=%r mediana_ms=%.0f limite_ms=%.0f amostras=%r fio_do_chamador=%s '
            'quem_perguntou=%r'
            % (vid, med, (mod._TID_INLINE_WAIT_S + 0.15) * 1000.0,
               ['%.0f' % x for x in samples], mine, ran_on[:2]))
    finally:
        mod.list_targets = old_list
        if cold is not None:
            cold.stop()

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    mod = load(SOURCE, '_cdp_latency_cdp')
    if not args.neg_arm:
        rows = run_arms(mod)
        fails = [r for r in rows if not r[1]]
        print('VERDICT: %s (arms=%d fail=%d)'
              % ('PASS' if not fails else 'FAIL', len(rows), len(fails)))
        return 0 if not fails else 1

    original = open(SOURCE, encoding='utf-8', newline='').read()
    mutants = [
        ('inline', ANCHOR_INLINE, MUT_INLINE, 'L4-COLD-BOUND'),
        ('sem-orcamento', ANCHOR_BUDGET, MUT_BUDGET, 'L3-PROBE-BUDGET'),
        ('sem-idade', ANCHOR_STALE, MUT_STALE, 'L2-STALE-LOG'),
    ]
    tmpdir = tempfile.mkdtemp(prefix='cdp-latency-neg-')
    shutil.copy(os.path.join(APP, 'youtube_window.py'),
                os.path.join(tmpdir, 'youtube_window.py'))
    verdict = True
    try:
        for label, old, new, want in mutants:
            if original.count(old) != 1:
                print('NEG-ARM IMPOSSIVEL: ancora %r aparece %d vez(es)'
                      % (label, original.count(old)))
                return 2
            path = os.path.join(tmpdir, 'youtube_cdp_source_%s.py'
                                % label.replace('-', '_'))
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(original.replace(old, new, 1))
            print('== mutante %s (%s tem de cair)' % (label, want))
            row = {r[0]: r for r in run_arms(load(path, '_cdp_lat_%s' % label))}
            hit = row.get(want)
            red = hit is not None and not hit[1]
            verdict = verdict and red
            print('   %s -> %s' % (want, 'RED (como desenhado)' if red
                                   else 'sobreviveu'))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if verdict:
        print('NEG-ARM: PASS (tres mutantes, os tres apanhados)')
        return 1
    print('NEG-ARM: FAIL -- um mutante sobreviveu')
    return 0


if __name__ == '__main__':
    sys.exit(main())
