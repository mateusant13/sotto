#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: julga a linha de custo e a DECISAO de reiniciar (pura), sem tocar audio e sem reiniciar worker nenhum -- nao corrige a degradacao que o worker paga.
"""cost-watchdog-oracle -- a regra "CPU sem linha" e as duas pontas da linha que a alimenta.

PORQUE EXISTE. O watcher mediu o worker do dono (`worker/sotto_worker.py`, pid 20676,
232 min de vida) a **270,6 %c com `rows=0`** e 6 176 s de CPU acumulada; o dono sentiu
a travada antes de qualquer instrumento deste repo. O worker morto e respawnado mediu
**1,2 %c** -- fator 240 --, ou seja, o que cura a degradacao e' um ARRANQUE NOVO lendo
o codigo do disco, e o produto nao tinha nem o numero nem a decisao.

Este oraculo julga TRES metades, e nenhuma delas precisa de dispositivo de audio:

  A. A FORMA da linha do worker (`worker.sotto_worker.format_worker_cost`), executada
     pela funcao REAL: a shell tem de a conseguir ler, e um campo ilegivel tem de ser
     AUSENTE em vez de virar zero (`cpu_s_per_row=none` quando nao ha linha nenhuma).
  B. O PARSER da shell (`sotto_webview.parse_worker_cost`), pela funcao REAL, incluindo
     o `None` para uma linha que nao e' de custo (o pump nao pode classificar `WORKER_STATS`
     como custo).
  C. A DECISAO (`cost_watchdog.plan`), que e' pura: a serie tem de CHEGAR ao reinicio
     pelos numeros medidos (270 %c / 0 linha) e NAO pode reiniciar um worker saudavel,
     um worker transcrevendo, nem o mesmo worker duas vezes dentro do piso.

`--neg-arm` muda uma coisa de cada vez numa COPIA em memoria e exige o vermelho:
  M1 limiar a 0.0 (qualquer CPU reinicia) -> a arm do worker ocioso cai;
  M2 limiar a 1e9  (nada reinicia)      -> a arm da degradacao cai;
  M3 delta ignorado (volta ao cumulativo) -> a arm do worker que JA' produziu cai;
  M4 piso removido                        -> a arm do piso cai;
  M5 `format_worker_cost` sem o campo `rows_since_tick` -> a arm da forma cai.
"""
from __future__ import annotations

import importlib.util
import io
import os
import re
import sys
import types
import textwrap
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'app', 'webview')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')


class Ctx:
    def __init__(self):
        self.arms = []          # (id, ok, detail)

    def arm(self, name, ok, detail=''):
        self.arms.append((name, bool(ok), detail))
        return ok


def load_worker_module():
    """O modulo do worker SEM arrancar nada: so' a funcao de forma e' carregada.

    Importar `sotto_worker` de verdade carrega o modelo; por isso o ficheiro e'
    lido e SO' o `def format_worker_cost` e' extraido e compilado num namespace
    proprio. Ler o ficheiro todo e' o que garante que se julga o que EMBARCA.
    """
    src = io.open(WORKER, encoding='utf-8').read()
    start = src.index('def format_worker_cost(')
    end = src.index('\ndef ', start + 10)
    snippet = src[start:end]
    ns = {'__name__': 'worker_cost_form'}
    exec(compile(snippet, WORKER, 'exec'), ns)
    return ns['format_worker_cost'], src


def load_shell_parser():
    """`parse_worker_cost` extraida do shell: o shell inteiro nao importa sob teste."""
    path = os.path.join(APP, 'sotto_webview.py')
    src = io.open(path, encoding='utf-8').read()
    m = re.search(r'^WORKER_COST_RE = .*$', src, re.M)
    if m is None:
        raise SystemExit('o shell perdeu a constante WORKER_COST_RE')
    start = src.index('def parse_worker_cost(')
    end = src.index('\ndef ', start + 10)
    snippet = 'import re\n' + m.group(0) + '\n' + src[start:end]
    ns = {'__name__': 'shell_cost_parse'}
    exec(compile(snippet, path, 'exec'), ns)
    return ns['parse_worker_cost'], src


def load_watchdog(mutate=None):
    """A decisao REAL, opcionalmente com UMA mutacao plantada em memoria."""
    path = os.path.join(APP, 'cost_watchdog.py')
    src = io.open(path, encoding='utf-8').read()
    if mutate is not None:
        src = mutate(src)
    mod = types.ModuleType('cost_watchdog_under_test')
    mod.__file__ = path
    exec(compile(src, path, 'exec'), mod.__dict__)
    return mod



def load_shell_handler(cost_watchdog, source=None):
    """`SottoShell.on_worker_cost` REAL, extraido do fonte que embarca.

    A regra pura (C) e o parser (B) nao provam a FIACAO: e' o handler que journaliza,
    zera a serie e chama `revive_worker`. Sem esta arm, a cura e' uma funcao que
    ninguem chama -- a classe de defeito que esta casa ja pagou varias vezes.
    """
    path = os.path.join(APP, 'sotto_webview.py')
    src = io.open(path, encoding='utf-8').read() if source is None else source
    start = src.index('    def on_worker_cost(self, parsed):')
    end = src.index('\n    def on_worker_stats(self, parsed):', start)
    body = src[start:end]
    # as constantes de classe que o corpo le
    m = re.search(r'^    COST_LOG_INTERVAL_S = ([0-9.]+)$', src, re.M)
    interval = float(m.group(1)) if m else 60.0
    # O `log` e' o da FUNCAO DE MODULO, nao um metodo do stub (medido 2026-11-10):
    # o `SottoShell` real NAO tem `self.log`, e o stub que o fornecia escondia o
    # `BRIDGE_COST_CALLBACK_FAILED error=AttributeError("'SottoShell' object has no
    # attribute 'log'")` do log do dono -- o handler levantava ANTES da decision de
    # reiniciar, logo o vigia de custo nunca disparou nada. O stub deixa de o ter.
    ns = {'time': time, 'cost_watchdog': cost_watchdog,
          'log': lambda msg: None}
    exec(compile(textwrap.dedent(body), path, 'exec'), ns)
    fn = ns['on_worker_cost']
    fn.COST_LOG_INTERVAL_S = interval
    return fn, interval


class ShellStub:
    """O minimo que o handler toca: `revive_worker` e os quatro campos.

    SEM `log`, DE PROPOSITO: o `SottoShell` real nao tem esse metodo, e um stub que o
    inventava fazia o oraculo passar sobre um handler que, em producao, levantava
    `AttributeError` na primeira volta (ver `load_shell_handler`).
    """

    COST_LOG_INTERVAL_S = 60.0

    def __init__(self, handler, boom=False, refuse=False):
        self.lines = []
        self.revives = []
        self.boom = boom
        self.refuse = refuse
        self._cost_streak = 0
        self._cost_last_restart = 0.0
        self._cost_restarts_hour = 0
        self._cost_logged_at = 0.0
        self.raises = []
        self._handler = handler

    def log_line(self, msg):
        self.lines.append(msg)

    def revive_worker(self, reason):
        if self.boom:
            raise RuntimeError('revive explodiu')
        if self.refuse:
            return False          # o `revive_worker` real RECUSA (parked/in-flight)
        self.revives.append(reason)
        return True


def drive(handler, interval, fields_list, boom=False, refuse=False):
    """Passa a serie pelo handler como o pump passaria, com o relogio controlado."""
    shell = ShellStub(handler, boom=boom, refuse=refuse)
    clock = {'t': 1000.0}

    class FakeTime:
        @staticmethod
        def monotonic():
            return clock['t']

    for fields in fields_list:
        handler.__globals__['time'] = FakeTime
        # o `log` de modulo, trocado por um coletor -- e' o que o fonte chama
        handler.__globals__['log'] = shell.log_line
        # UM HANDLER QUE LEVANTA NAO DERRUBA O JULGAMENTO: a excepcao fica REGISTADA
        # no stub e as arms que esperam linhas caem sozinhas. Quem possui o "nao
        # levanta" e' a D7, que conduz o handler uma vez contra o stub fiel -- e um
        # `raise` aqui matava o proprio oraculo em vez de reprovar o mutante (medido
        # 2026-11-10 no M11, que volta a chamar `self.log`).
        try:
            handler(shell, {'fields': fields, 'childPid': 4242})
        except Exception as exc:  # noqa: BLE001
            shell.raises.append(exc)
        clock['t'] += 10.0
    return shell


def run_arms(cache, mod, cw):
    """`mod` e' o coletor (tem `.arm`); `cw` e' a decisao a julgar."""
    """As arms. `cache` guarda o que o negativo reutiliza (a forma, o parser)."""
    fmt = cache['fmt']
    parse = cache['parse']
    g = lambda k: getattr(mod, k, None)
    BUSY, STALL, FLOOR, MAXH = cw.BUSY_PCT, cw.STALL_TICKS, cw.FLOOR_S, cw.MAX_PER_HOUR

    # ── A. a FORMA que o worker imprime ────────────────────────────────────────
    line = fmt('tick', 6176.04, 27.06, 10.0, 0, 0, None, 13920.0, 20676,
               extras={'chunks_since_tick': 17, 'ms_per_chunk': 49.8,
                       'audio_s_since_tick': 9.52, 'rtf': 0.089})
    cache['line'] = line
    mod.arm('A1 linha comeca por WORKER_COST e traz o tag',
            line.startswith('WORKER_COST tag=tick'), line[:60])
    fields = cache['parse'](line)['fields'] if cache.get('parse') else {}
    want = ('cpu_s', 'cpu_pct_avg', 'rows', 'rows_since_tick', 'rows_per_min',
            'cpu_s_per_row', 'chunks_since_tick', 'ms_per_chunk',
            'audio_s_since_tick', 'rtf', 'uptime_s', 'pid')
    have = [k for k in want if k in fields]
    mod.arm('A2 a shell le TODOS os campos que a decisao usa',
            len(have) == len(want), 'faltam=%r' % ([k for k in want if k not in fields],))
    mod.arm('A3 270,6 %c e 0 linha leem-se como 270,6 e 0',
            abs(float(fields.get('cpu_pct_avg', -1)) - 270.6) < 0.05
            and fields.get('rows') == '0' and fields.get('rows_since_tick') == '0',
            '%s / %s / %s' % (fields.get('cpu_pct_avg'), fields.get('rows'),
                              fields.get('rows_since_tick')))
    mod.arm('A4 sem linha produzida o custo por linha e a PALAVRA none',
            fields.get('cpu_s_per_row') == 'none', fields.get('cpu_s_per_row'))
    line2 = fmt('tick', 10.5, 2.0, 10.0, 1768, 3, 0.6667, 120.0, 14712,
                extras={'chunks_since_tick': 17, 'ms_per_chunk': 61.2,
                        'audio_s_since_tick': 9.52, 'rtf': 0.109})
    f2 = parse(line2)['fields']
    mod.arm('A5 com linha produzida o custo por linha e um numero',
            re.match(r'^\d+\.\d+$', f2.get('cpu_s_per_row') or '') is not None,
            f2.get('cpu_s_per_row'))
    mod.arm('A6 o pid viaja (duas instancias no mesmo ficheiro de log)',
            f2.get('pid') == '14712', f2.get('pid'))
    # O DENOMINADOR que o watcher pediu em 2026-11-09: 3 nucleos para UM fluxo so' e'
    # um numero quando vem com ms por chunk e com o audio que pagou por ele.
    line3 = fmt('tick', 6176.0, 27.06, 10.0, 0, 0, None, 13920.0, 20676,
                extras={'chunks_since_tick': 17, 'ms_per_chunk': 49.8,
                        'audio_s_since_tick': 9.52, 'rtf': 0.089})
    f3 = parse(line3)['fields']
    mod.arm('A9 ms_per_chunk, chunks e rtf viajam na linha',
            f3.get('chunks_since_tick') == '17'
            and abs(float(f3.get('ms_per_chunk')) - 49.8) < 0.01
            and abs(float(f3.get('rtf')) - 0.089) < 0.001,
            '%s / %s / %s' % (f3.get('chunks_since_tick'), f3.get('ms_per_chunk'),
                              f3.get('rtf')))
    line4 = fmt('tick', 1.0, 0.4, 10.0, 3, 3, 0.13, 60.0, 1,
                extras={'ms_per_chunk': None})
    # O CENSO DOS FIOS DO GENAI (2026-11-09). `og.Model` cria 3-4 sessoes a largura
    # da maquina (`intra_op=10` => 9 fios de trabalho cada) e NENHUM dos tres
    # caminhos de configuracao as governa -- por isso o lever e' a afinidade dos fios
    # ja' criados, e o numero tem de existir no log. As tres arms julgam a metade
    # pura (`cpu_mask`), a publicacao da linha e a fiacao do relay na shell.
    worker_src = io.open(os.path.join(ROOT, 'worker', 'sotto_worker.py'),
                         encoding='utf-8').read()
    i = worker_src.index('def cpu_mask(')
    j = worker_src.index('\n# ── CUDA plumbing', i)
    ns = {'os': os}
    exec(compile(worker_src[i:j], 'worker_cpu_mask', 'exec'), ns)
    mod.arm('A11 cpu_mask le faixas e listas, e recusa lixo',
            ns['cpu_mask']('4-9') == 0b1111110000
            and ns['cpu_mask']('0,1,2') == 7
            and ns['cpu_mask']('lixo') == 0,
            '%d / %d / %d' % (ns['cpu_mask']('4-9'), ns['cpu_mask']('0,1,2'),
                              ns['cpu_mask']('lixo')))
    i2 = worker_src.index('def cap_genai_threads(')
    j2 = worker_src.index('\n# ── CUDA plumbing', i2)
    out = []
    ns2 = {'os': os, 'err': lambda msg: out.append(msg),
           'genai_thread_ids': lambda: [11, 22], 'cpu_mask': ns['cpu_mask'],
           'os_env': os.environ}
    exec(compile(worker_src[i2:j2], 'worker_cap', 'exec'), ns2)
    old_env = os.environ.pop('SOTTO_GENAI_CPUS', None)
    try:
        ns2['cap_genai_threads']('arm')
    finally:
        if old_env is not None:
            os.environ['SOTTO_GENAI_CPUS'] = old_env
    mod.arm('A12 a linha publica o censo mesmo SEM aperto (cpus=none)',
            len(out) == 1 and out[0].startswith('WORKER_GENAI_THREADS threads=2')
            and 'cpus=none' in out[0] and 'tag=arm' in out[0],
            out[0] if out else 'nenhuma linha')
    # O TUPLE LIDO POR AST, nao por `index(')')`: a primeira versao cortava no
    # primeiro parentese do proprio comentario e publicava AUSENTE sobre um tag
    # que estava la' -- um portao que mente sobre o texto perde a autoridade.
    import ast as _ast
    shell_src = io.open(os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py'),
                        encoding='utf-8').read()
    tags = set()
    for node in _ast.parse(shell_src).body:
        if isinstance(node, _ast.Assign) and any(
                getattr(t, 'id', '') == 'ENGINE_VISIBLE_TAGS' for t in node.targets):
            tags = set(_ast.literal_eval(node.value))
    mod.arm('A13 a shell relata WORKER_GENAI_THREADS (a linha chega ao log)',
            'WORKER_GENAI_THREADS' in tags,
            '%d tags: %s' % (len(tags), 'presente' if 'WORKER_GENAI_THREADS' in tags
                             else 'AUSENTE'))
    mod.arm('A10 tick sem chunk diz ms_per_chunk=none (nao zero)',
            parse(line4)['fields'].get('ms_per_chunk') == 'none',
            parse(line4)['fields'].get('ms_per_chunk'))

    # ── A-bis. A CHAMADA (o que um modulo executavel nao prova) ────────────────
    # A forma e' pura, mas nada obriga o laco a chama-la: uma funcao que produz a
    # linha certa e ninguem invoca e' a classe "cura que ninguem chama". O braco le'
    # o FONTE que embarca e exige a chamada no bloco do tick, GUARDADA -- o relator
    # do laco de audio nao pode derrubar o audio (a licao de `emit-pipe-dead`).
    src = cache['worker_src']
    call = ('err(stats_line("tick"))' in src
            and 'err(cost_line("tick"))' in src
            and 'WORKER_COST_FAILED' in src)
    mod.arm('A7 o laco do tap CHAMA a linha de custo, guardada', call,
            'chamada presente' if call else 'a funcao existe e o laco nao a chama')
    i_stats = src.find('err(stats_line("tick"))')
    i_cost = src.find('err(cost_line("tick"))')
    mod.arm('A8 a linha nao substitui o WORKER_STATS (os dois saem no mesmo tick)',
            -1 < i_stats < i_cost, 'stats@%d cost@%d' % (i_stats, i_cost))

    # ── B. o PARSER da shell ───────────────────────────────────────────────────
    mod.arm('B1 linha de custo -> dict com tag', (parse(line) or {}).get('tag') == 'tick')
    mod.arm('B2 WORKER_STATS NAO e custo', parse(
        'WORKER_STATS tag=tick blocks=1 captions=0') is None)
    mod.arm('B3 lixo NAO e custo', parse('random text') is None)
    mod.arm('B4 campo sem "=" nao inventa chave',
            parse('WORKER_COST tag=tick lixo cpu_pct_avg=1.0')['fields'].get('lixo') is None)

    # ── B-bis. A FIACAO estatica: o pump classifica e o shell recebe ───────────
    sh = cache['shell_src']
    mod.arm('B5 o pump classifica WORKER_COST e chama on_cost',
            "line.startswith('WORKER_COST')" in sh and 'self.on_cost(' in sh)
    mod.arm('B6 o callback e passado nas DUAS construcoes da ponte (fria e quente)',
            sh.count('on_cost=self.on_worker_cost') == 2,
            '%d ocorrencia(s)' % sh.count('on_cost=self.on_worker_cost'))
    mod.arm('B7 o construtor da ponte aceita on_cost com no-op por omissao',
            'on_cost=None' in sh and 'self.on_cost = on_cost or' in sh)
    mod.arm('B8 a shell tem o handler e ele chama revive_worker',
            'def on_worker_cost(' in sh and "revive_worker('cost-watchdog')" in sh)

    # ── C. a DECISAO ───────────────────────────────────────────────────────────
    def series(n, pct='270.6', delta='0', rows_val='0', gap=10.0):
        st, out = 0, []
        for i in range(n):
            v = cw.plan({'cpu_pct_avg': pct, 'rows': rows_val,
                         'rows_since_tick': delta}, st, 1000.0 + i * gap, 0.0, 0)
            st = v['streak']
            out.append(v)
        return out

    def series_plain(n, pct, delta, rows_val='0', gap=10.0, floor_from=None):
        st, out, last = 0, [], 0.0
        for i in range(n):
            now = 1000.0 + i * gap
            v = cw.plan({'cpu_pct_avg': pct, 'rows': rows_val,
                         'rows_since_tick': delta}, st, now, last, 0)
            st = v['streak']
            if v['restart']:
                last = now
                st = 0      # a shell zera a serie no reinicio (`self._cost_streak = 0`)
            out.append(v)
        return out

    s = series_plain(STALL + 5, '270.6', '0')
    first = next((i for i, v in enumerate(s) if v['restart']), None)
    mod.arm('C1 o DEFEITO medido (270 %%c, 0 linha) reinicia no tick STALL_TICKS',
            first == STALL - 1, 'primeiro restart no tick %r (STALL_TICKS=%d)'
            % (first, STALL))
    mod.arm('C2 antes do limiar NAO reinicia (STALL-1 ticks de CPU alta)',
            all(not v['restart'] for v in s[:STALL - 1]),
            'streak=%r' % (s[STALL - 2]['streak'],))

    s2 = series_plain(60, '1.2', '0')
    mod.arm('C3 worker OCIOSO saudavel (1,2 %c, 0 linha) nunca reinicia',
            not any(v['restart'] for v in s2),
            'streaks=%r' % sorted({v['streak'] for v in s2}))

    s3 = series_plain(60, '140.0', '5')
    mod.arm('C4 worker TRANSCREVENDO (140 %c, 5 linhas/tick) nunca reinicia',
            not any(v['restart'] for v in s3))

    s4 = series_plain(STALL + 2, '140.0', '0', rows_val='1768')
    mod.arm('C5 worker que JA produziu e parou de produzir reinicia '
            '(o caso do dono: 1 768 linhas e depois nada)',
            any(v['restart'] for v in s4),
            'rows cumulativo=1768, delta=0')

    s5 = series_plain(STALL + 2, '140.0', '0', rows_val='0')
    mod.arm('C6 sem o campo do delta o cumulativo decide (compatibilidade)',
            any(v['restart'] for v in s5))

    # piso: reinicia uma vez, e dentro de FLOOR_S nao reinicia outra vez
    s6 = series_plain(int(STALL * 8), '270.6', '0')
    restarts = [i for i, v in enumerate(s6) if v['restart']]
    gaps = [b - a for a, b in zip(restarts, restarts[1:])]
    mod.arm('C7 o piso segura o segundo reinicio (>= %d ticks = %.0f s)' % (FLOOR / 10, FLOOR),
            len(restarts) >= 2 and all(g * 10.0 >= FLOOR for g in gaps),
            'ticks=%r gaps_s=%r' % (restarts, [g * 10.0 for g in gaps]))

    # tecto por hora
    v = cw.plan({'cpu_pct_avg': '270.6', 'rows': '0', 'rows_since_tick': '0'},
                STALL, 100000.0, 0.0, MAXH)
    mod.arm('C8 tecto de %d reinicios/hora recusa o seguinte e diz por que' % MAXH,
            not v['restart'] and v['why'] == 'tecto-por-hora', v['why'])

    v = cw.plan({'cpu_pct_avg': 'nao-e-numero', 'rows': '0'}, 5, 0.0, 0.0, 0)
    mod.arm('C9 campo ilegivel NAO cumpre nem zera a serie',
            not v['restart'] and v['streak'] == 5 and v['why'] == 'sem-cpu-legivel',
            '%r %s' % (v, v['why']))

    v_busy = cw.plan({'cpu_pct_avg': str(BUSY), 'rows': '0', 'rows_since_tick': '0'},
                     0, 0.0, 0.0, 0)
    v_under = cw.plan({'cpu_pct_avg': str(BUSY - 0.1), 'rows': '0', 'rows_since_tick': '0'},
                      0, 0.0, 0.0, 0)
    mod.arm('C10 o limiar e INCLUSIVO e nao se move sozinho',
            v_busy['streak'] == 1 and v_under['streak'] == 0,
            'busy=%d under=%d' % (v_busy['streak'], v_under['streak']))

    # ── D. a FIACAO na shell (o handler REAL, com o relogio conduzido) ─────────
    handler, interval = cache['handler'], cache['interval']
    healthy = drive(handler, interval, [{'cpu_pct_avg': '1.2', 'rows': '5',
                                         'rows_since_tick': '1'}] * 5)
    mod.arm('D1 worker saudavel: zero reinicios e a serie fica em 0',
            not healthy.revives and healthy._cost_streak == 0, '%r' % (healthy.revives,))
    busy = drive(handler, interval, [{'cpu_pct_avg': '270.6', 'rows': '0',
                                      'rows_since_tick': '0'}] * (STALL + 2))
    mod.arm('D2 o DEFEITO medido reinicia UMA vez pelo caminho que ja existe',
            busy.revives == ['cost-watchdog'],
            'revives=%r streak=%d' % (busy.revives, busy._cost_streak))
    mod.arm('D3 o reinicio e JOURNALIZADO com o numero que o justificou',
            any('WORKER_COST_RESTART' in ln and 'cpu_pct_avg=270.6' in ln
                for ln in busy.lines),
            [ln for ln in busy.lines if 'RESTART' in ln][:1])
    mod.arm('D4 a serie e uma linha por minuto, nao por tick',
            sum(1 for ln in busy.lines if ln.startswith('BRIDGE_WORKER_COST')) <= 4,
            '%d linhas em %d ticks (intervalo %.0f s)' % (
                sum(1 for ln in busy.lines if ln.startswith('BRIDGE_WORKER_COST')),
                len(busy.lines) and STALL + 2, interval))
    broke = drive(handler, interval, [{'cpu_pct_avg': '270.6', 'rows': '0',
                                       'rows_since_tick': '0'}] * (STALL + 2), boom=True)
    mod.arm('D5 um revive que levanta NAO derruba o pump (linha de falha, sem raise)',
            any('WORKER_COST_RESTART_FAILED' in ln for ln in broke.lines))
    # A RECUSA E' DO `revive_worker` (parked/in-flight), e o log nao pode mentir
    # nem gastar o orcamento do piso numa recusa.
    refused = drive(handler, interval, [{'cpu_pct_avg': '270.6', 'rows': '0',
                                         'rows_since_tick': '0'}] * (STALL + 2),
                    refuse=True)
    line = next((ln for ln in refused.lines if 'WORKER_COST_RESTART' in ln), '')
    # D7 -- O DEFEITO MEDIDO A 2026-11-10: o handler chamava `self.log` e o
    # `SottoShell` NAO tem esse metodo. Todo `WORKER_COST` levantava dentro do
    # `on_cost` do `WorkerBridge`, que engolia a excepcao e escrevia
    # `BRIDGE_COST_CALLBACK_FAILED` -- logo o vigia de custo NUNCA decidia reiniciar,
    # e a linha que ele existe para publicar nunca saiu. Esta arm conduz o handler
    # REAL sobre um stub que tem SO o que o `SottoShell` tem; uma dependencia
    # inventada (`self.log`, `self._x`) cai aqui e nao em producao.
    probe = ShellStub(handler)
    handler.__globals__['time'] = time
    handler.__globals__['log'] = probe.log_line
    try:
        handler(probe, {'fields': {'cpu_pct_avg': '270.6', 'rows': '0',
                                   'rows_since_tick': '0'}, 'childPid': 4242})
        raised = ''
    except Exception as exc:  # noqa: BLE001 -- e' o que a arm mede
        raised = '%s: %s' % (type(exc).__name__, exc)
    mod.arm('D7 o handler nao depende de um metodo que o SottoShell nao tem',
            not raised and any(ln.startswith('BRIDGE_WORKER_COST')
                               for ln in probe.lines),
            raised or ('linhas=%r' % (probe.lines[:1],)))
    mod.arm('D8 a serie conduzida nao levanta nenhuma volta',
            not healthy.raises and not busy.raises and not broke.raises
            and not refused.raises,
            '%r' % ([type(e).__name__ for e in
                     (healthy.raises + busy.raises + broke.raises + refused.raises)][:3],))
    # ── E. A JANELA DO TECTO (D-19) ───────────────────────────────────────────
    # O `MAX_PER_HOUR` diz "por hora" e o contador nunca era zerado: o tecto era
    # de 3 reinicios pela VIDA da shell (o autostart a mantem de pe o dia todo).
    W = getattr(cw, 'WINDOW_S', None)
    WE = getattr(cw, 'window_expired', None)
    mod.arm('E1 a janela e um NUMERO declarado, nao um comentario',
            W == 3600.0, 'WINDOW_S=%r' % (W,))
    if WE is None:
        mod.arm('E1 window_expired existe e e pura', False, 'ausente')
    else:
        cases = [
            (100.0, 0.0, False, 'nunca iniciada'),
            (100.0, 100.0, False, 'agora'),
            (W - 1 + 100.0, 100.0, False, 'um segundo antes'),
            (W + 100.0, 100.0, True, 'exactamente a janela'),
            (W + 1 + 100.0, 100.0, True, 'um segundo depois'),
            (50.0, 100.0, False, 'relogio para tras'),
            (1e6, -50.0, True, 'inicio negativo = passado'),
            ('x', 100.0, False, 'agora ilegivel'),
            (100.0, 'x', False, 'inicio ilegivel'),
        ]
        bad = [(a, b, want, why) for a, b, want, why in cases
               if bool(WE(a, b)) != want]
        mod.arm('E1 window_expired: a borda e a janela, e um valor ilegivel nao a '
                'reabre', not bad, '%r' % (bad[:3],))

    # E2 -- O HANDLER REAL, com o contador CHEIO e a janela vencida: o reinicio
    # volta a ser permitido, e a linha diz que a janela virou.
    shell2 = ShellStub(handler)
    shell2._cost_restarts_hour = MAXH          # o tecto atingido
    shell2._cost_hour_at = 1e6 - (W + 5.0)      # ... numa janela que ja' virou
    clock2 = {'t': 1e6}

    class FakeTime2:
        @staticmethod
        def monotonic():
            return clock2['t']

    handler.__globals__['time'] = FakeTime2
    handler.__globals__['log'] = shell2.log_line
    for _ in range(STALL + 1):
        try:
            handler(shell2, {'fields': {'cpu_pct_avg': '270.6', 'rows': '0',
                                        'rows_since_tick': '0'},
                             'childPid': 4242})
        except Exception as exc:  # noqa: BLE001
            shell2.raises.append(exc)
        clock2['t'] += 10.0
    mod.arm('E2 a janela vencida devolve o tecto (o reinicio volta a ser permitido)',
            not shell2.raises and shell2.revives == ['cost-watchdog']
            and any('WORKER_COST_WINDOW_RESET' in ln for ln in shell2.lines),
            'revives=%r raises=%r lines=%r'
            % (shell2.revives, [type(e).__name__ for e in shell2.raises],
               [ln for ln in shell2.lines if 'WINDOW' in ln or 'RESTART' in ln][:2]))

    # E3 -- DENTRO da janela o tecto continua a valer: o contador cheio RECUSA,
    # senao a cura seria "reiniciar para sempre", que e' o defeito oposto.
    shell3 = ShellStub(handler)
    shell3._cost_restarts_hour = MAXH
    shell3._cost_hour_at = 1e6
    clock3 = {'t': 1e6}

    class FakeTime3:
        @staticmethod
        def monotonic():
            return clock3['t']

    handler.__globals__['time'] = FakeTime3
    handler.__globals__['log'] = shell3.log_line
    for _ in range(STALL + 1):
        try:
            handler(shell3, {'fields': {'cpu_pct_avg': '270.6', 'rows': '0',
                                        'rows_since_tick': '0'},
                             'childPid': 4242})
        except Exception as exc:  # noqa: BLE001
            shell3.raises.append(exc)
        clock3['t'] += 10.0
    mod.arm('E3 dentro da janela o tecto continua a recusar',
            not shell3.revives
            and any('tecto-por-hora' in ln for ln in shell3.lines),
            'revives=%r lines=%r'
            % (shell3.revives, [ln for ln in shell3.lines if 'RESTART' in ln][:1]))

    mod.arm('D6 recusa do revive aparece como accepted=false e NAO gasta o piso',
            'accepted=false' in line and refused._cost_last_restart == 0.0
            and refused._cost_restarts_hour == 0, line or 'sem linha de restart')
    return mod


def verify(arms, tag):
    fails = [(n, d) for n, ok, d in arms if not ok]
    print('%s arms=%d pass=%d fail=%d' % (tag, len(arms), len(arms) - len(fails), len(fails)))
    for n, d in fails:
        print('   FAIL %s   %s' % (n, d))
    return not fails


def main(argv):
    neg = '--neg-arm' in argv
    fmt, worker_src = load_worker_module()
    parse, shell_src = load_shell_parser()
    cw_real = load_watchdog()
    handler, interval = load_shell_handler(cw_real)
    cache = {'fmt': fmt, 'parse': parse, 'handler': handler, 'interval': interval,
             'worker_src': worker_src, 'shell_src': shell_src}

    # A arm A2/A3 dependem do parser; o parser depende da constante do shell.
    print('sotto: cost-watchdog -- a regra que a degradacao de 2026-11-09 pediu')

    if neg:
        # ── os mutantes, um por arm, cada um tem de derrubar A SUA arm ─────────
        muts = [
            ('M1 limiar 0.0 (qualquer CPU reinicia)',
             lambda s: s.replace('BUSY_PCT = 60.0', 'BUSY_PCT = 0.0', 1),
             'C3'),
            ('M2 limiar 1e9 (nada reinicia)',
             lambda s: s.replace('BUSY_PCT = 60.0', 'BUSY_PCT = 1e9', 1),
             'C1'),
            ('M3 delta ignorado (so o cumulativo)',
             lambda s: s.replace("if 'rows_since_tick' in fields:",
                                 "if False and 'rows_since_tick' in fields:", 1),
             'C5'),
            ('M4 piso removido',
             lambda s: s.replace('    if last_restart_at and (now - last_restart_at) < FLOOR_S:',
                                 '    if False:', 1),
             'C7'),
            # D-19: a janela que nunca vira -- o defeito antigo (o tecto valia
            # pela vida do processo) escrito como mutante.
            ('M12 a janela nunca expira',
             lambda s: s.replace('    if started == 0.0 or moment <= started:',
                                 '    if True:', 1),
             'E1'),
        ]
        caught = 0
        cw_real = load_watchdog()
        for name, mutate, expected in muts:
            cw = load_watchdog(mutate)
            fresh = Ctx()
            run_arms(cache, fresh, cw)
            red = [n for n, ok, d in fresh.arms if not ok]
            hit = any(n.split()[0] == expected for n in red)
            caught += 1 if hit else 0
            print('   %-46s RED em %-14s %s' % (name, expected,
                                                'caught' if hit else 'NOT-CAUGHT red=%r' % (red,)))
        # M5: a forma perde o campo do delta
        broken = worker_src.replace('"rows=%d rows_since_tick=%d rows_per_min=%.1f '
                                    'cpu_s_per_row=%s "',
                                    '"rows=%d rows_per_min=%.1f cpu_s_per_row=%s "', 1)
        caught_m5 = '"rows_since_tick=%d' not in broken and broken != worker_src
        # o mutante tem de MUDAR o fonte E a arm da forma tem de cair com ele
        ok_m5 = False
        if caught_m5:
            start = broken.index('def format_worker_cost(')
            end = broken.index('\ndef ', start + 10)
            ns = {'__name__': 'm5'}
            exec(compile(broken[start:end], WORKER, 'exec'), ns)
            try:
                line = ns['format_worker_cost']('tick', 1.0, 1.0, 10.0, 0, 0, None, 1.0, 2)
            except TypeError:
                ok_m5 = True   # aridade mudou -> a linha nao e' a mesma, e' RED
            else:
                ok_m5 = 'rows_since_tick' not in line
            print('   %-46s RED em %-14s %s' % ('M5 a forma perde rows_since_tick', 'A2/A3',
                                                'caught' if ok_m5 else 'NOT-CAUGHT'))
        caught += 1 if ok_m5 else 0

        # M6/M7: a FIACAO. Cada mutante tem de derrubar A SUA arm (D2 e D4).
        wire = [
            ('M6 o handler NAO chama revive_worker', 'D2',
             lambda src: src.replace(
                 "            accepted = self.revive_worker('cost-watchdog') is not False",
                 '            accepted = False', 1)),
            ('M10 a recusa e ignorada (contagem sempre sobe)', 'D6',
             lambda src: src.replace('        if accepted:\r\n            self._cost_last_restart = now'
                                     if '\r\n' in src else
                                     '        if accepted:\n            self._cost_last_restart = now',
                                     '        if True:\n            self._cost_last_restart = now', 1)),
            # M11 -- O DEFEITO DE PRODUCAO (2026-11-10): o handler voltar a chamar
            # um metodo que o `SottoShell` nao tem. Tem de cair na D7.
            ('M11 o handler volta a chamar self.log', 'D7',
             lambda src: src.replace(
                 "            log('BRIDGE_WORKER_COST cpu_pct_avg=%s",
                 "            self.log('BRIDGE_WORKER_COST cpu_pct_avg=%s", 1)),
            # D-19: a shell deixa de perguntar a janela -- o contador nunca zera.
            ('M13 a shell nao pergunta a janela', 'E2',
             lambda src: src.replace(
                 '        if not hour_at or cost_watchdog.window_expired(now, hour_at):',
                 '        if False:', 1)),
            ('M7 o handler journaliza a CADA tick (sem intervalo)', 'D4',
             lambda src: src.replace('        if now - getattr(self, \'_cost_logged_at\', 0.0) '
                                     '>= self.COST_LOG_INTERVAL_S:',
                                     '        if True:', 1)),
        ]
        for name, expected, mutate_src in wire:
            shell_src2 = mutate_src(shell_src)
            if shell_src2 == shell_src:
                print('   %-46s RED em %-14s MUTACAO-NAO-APLICOU' % (name, expected))
                continue
            try:
                h2, iv2 = load_shell_handler(cw_real, shell_src2)
            except Exception as exc:  # a mutacao quebrou o fonte = apanhada
                caught += 1
                print('   %-46s RED em %-14s caught (fonte invalido: %r)'
                      % (name, expected, exc))
                continue
            c2 = dict(cache)
            c2['handler'], c2['interval'] = h2, iv2
            fresh = Ctx()
            run_arms(c2, fresh, cw_real)
            red = [n for n, ok, d in fresh.arms if not ok]
            hit = any(n.split()[0] == expected for n in red)
            caught += 1 if hit else 0
            print('   %-46s RED em %-14s %s' % (name, expected,
                                                'caught' if hit else 'NOT-CAUGHT red=%r' % (red,)))

        # M8/M9: a CHAMADA e a FIACAO ESTATICA. Um mutante que apaga a chamada
        # (`cost_line` definida e nunca invocada) tem de derrubar A7; apagar UMA das
        # duas construcoes da ponte tem de derrubar B6.
        text = [
            ('M8 o laco NAO chama a linha de custo', 'A7',
             lambda src: src.replace('                                err(cost_line("tick"))',
                                     '                                pass', 1)),
            ('M9 a ponte QUENTE perde o on_cost', 'B6',
             lambda src: src.replace('                on_cost=self.on_worker_cost,',
                                     '                ', 1)),
        ]
        for name, expected, mutate_src in text:
            if expected == 'A7':
                c3 = dict(cache)
                c3['worker_src'] = mutate_src(worker_src)
                if c3['worker_src'] == worker_src:
                    print('   %-46s RED em %-14s MUTACAO-NAO-APLICOU' % (name, expected))
                    continue
                fresh = Ctx()
                run_arms(c3, fresh, cw_real)
            else:
                c3 = dict(cache)
                c3['shell_src'] = mutate_src(shell_src)
                if c3['shell_src'] == shell_src:
                    print('   %-46s RED em %-14s MUTACAO-NAO-APLICOU' % (name, expected))
                    continue
                fresh = Ctx()
                run_arms(c3, fresh, cw_real)
            red = [n for n, ok, d in fresh.arms if not ok]
            hit = any(n.split()[0] == expected for n in red)
            caught += 1 if hit else 0
            print('   %-46s RED em %-14s %s' % (name, expected,
                                                'caught' if hit else 'NOT-CAUGHT red=%r' % (red,)))

        total = len(muts) + 1 + len(wire) + len(text)
        print('NEG-ARM: %s -- %d/%d mutantes apanhados' % (
            'PASS' if caught == total else 'FAIL', caught, total))
        return 1 if caught == total else 0

    mod = load_watchdog()
    arms = Ctx()
    run_arms(cache, arms, mod)
    ok = verify(arms.arms, 'VERDICT:')
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
