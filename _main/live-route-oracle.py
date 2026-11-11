#!/usr/bin/env python3
"""live-route-oracle -- a legenda que PINTA tem de ser do audio que toca AGORA.

O DEFEITO (medido, sessao pid 54524, 2026-11-11): o motor de LOTE pintou uma
linha cujo audio era de `start=381.84` -- 299 s antes do pixel -- porque o unico
caminho para o ecra era o `emit` das linhas ao vivo, sem rota e sem idade; e a
faixa do proprio YouTube pintava no MESMO intervalo. Dono, verbatim: *"fica
aparecendo na tela de forma aleatoria so' por que ta tocando um audio, que nem
speaker e'"* / *"ta dando replay em audios que ja' tocaram a minutos atras"*.

O QUE ESTE PORTAO JULGA. As tres decisoes que fecham aquilo, lidas do FONTE REAL
por `ast` (nunca por texto: um comentario que cita a chamada faria a arm passar):

  A1 IDADE      `worker/live_route.py:caption_age_s` -- `tap_ms`, `audio_age_s`
                carimbado pelo produtor, e o par `end`+relogio. Sem nenhum dos
                tres a idade e' `None` (desconhecida), nunca zero.
  A2 ROTA       `worker/live_route.py:live_route_verdict` -- lote nunca pinta;
                com o player como dono a linha local nao pinta; senao a idade
                decide, contra `LIVE_MAX_AGE_S`.
  A3 RUIDO      `worker/caption_noise.py:is_noise_caption` -- o `Mmm` puro, e
                NUNCA uma linha com palavra real.
  A4 PONTO UNICO `live_route.admit` marca `history_only` + `route_refused` +
                `age_s`, e diz `LIVE_ROUTE_REFUSED` UMA vez por episodio.
  A5 CUSTO      as duas decisoes < 5 us por legenda.
  A6 SEM PERDA  `live_queue.PendingAudio.take_head` (o lote limitado): devolve
                so' o mais antigo, na ordem, e o resto fica na fila -- o numero
                de amostras nao muda.
  I1 O CHAMADOR REAL: o `emit` de `worker/sotto_worker.py`, importado como
                modulo e conduzido com `sys.stdout` trocado. Uma legenda entra,
                UMA linha JSON sai, sem excecao -- e a recusa leva
                `LIVE_ROUTE_REFUSED` ao stderr (nao ao stdout). Sem esta arm o
                commit `fb3206d` passou 42 arms verdes com `log=err` (um nome
                LOCAL de outra funcao) a rebentar no primeiro caption: a decisao
                estava certa e a EMENDA nao existia. O mutante M9 repoe o defeito.
  W1..W7       AS EMENDAS: onde a guarda e' CHAMADA. O `worker/sotto_worker.py` e
                `app/webview/sotto_webview.py` sao de outras lanes nesta ronda,
                por isso a emenda viaja como PATCH: a arm passa `pending` quando
                o hunk esta no patch e ainda nao na arvore, e VERMELHA quando nao
                esta em sitio nenhum -- um guarda que ninguem chama nao e' guarda.

    python _main\\live-route-oracle.py            # VERDICT: PASS (N/N) rc=0
    python _main\\live-route-oracle.py --neg-arm   # NEG-ARM: PASS (m/m) rc=1
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import timeit
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
SWITCH = os.path.join(ROOT, 'worker', 'engine_switch.py')
QUEUE = os.path.join(ROOT, 'worker', 'live_queue.py')
ROUTE = os.path.join(ROOT, 'worker', 'live_route.py')
NOISE = os.path.join(ROOT, 'worker', 'caption_noise.py')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
SHELL_PATCH = os.path.join(HERE, '_scratch', 'live-route-shell.patch')
WORKER_PATCH = os.path.join(HERE, '_scratch', 'live-route-worker.patch')

#: O que cada decisao precisa para correr: nomes de topo (funcoes e constantes).
ROUTE_NAMES = ('LIVE_MAX_AGE_S', 'CLOCK_JITTER_MS', 'BATCH_ROUTE', 'BATCH_PRODUCER',
               'OWNER_LOCAL', 'OWNER_PLAYER', 'REASON_FRESH', 'REASON_STALE',
               'REASON_BATCH', 'REASON_PLAYER', 'REASON_UNKNOWN', 'REASON_NOISE',
               'caption_producer',
               'caption_age_s', '_measured_age_s', '_caption_is_noise',
               'live_route_verdict')
NOISE_NAMES = ('_NOISE_WORD', 'is_noise_caption')


def _src(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def _extract(src, names):
    """O FONTE REAL, so' os nomes pedidos, extraido por AST e executado.

    Por AST e nao por texto: um comentario que cita a chamada, ou uma string com
    o nome, nao entra no namespace. E' o que separa "o codigo diz" de "o codigo
    e'".
    """
    tree = ast.parse(src)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            keep.append(node)
        elif isinstance(node, ast.Try):
            # o `try: from caption_noise import ...` do modulo real: sem ele o
            # fallback `_is_noise_caption = None` nunca corre e a porta de ruido
            # ficava a levantar `NameError` no namespace extraido.
            keep.append(node)
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(t in names for t in targets):
                keep.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in names:
                keep.append(node)
    module = ast.Module(body=keep, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, '<extracted>', 'exec'), ns)   # noqa: S102 -- o fonte real
    return ns


def _route_ns():
    """O modulo da rota, com o irmao `caption_noise` no `sys.path` como no worker."""
    worker_dir = os.path.dirname(ROUTE)
    added = worker_dir not in sys.path
    if added:
        sys.path.insert(0, worker_dir)
    try:
        return _extract(_src(ROUTE), ROUTE_NAMES)
    finally:
        if added:
            try:
                sys.path.remove(worker_dir)
            except ValueError:
                pass


def _noise_ns():
    return _extract(_src(NOISE), NOISE_NAMES)


# ── A1/A2/A3: a tabela de casos, a MESMA para o positivo e para os mutantes ──
NOW_MS = 1794429965822.0        # 17:46:05.822, o instante do defeito medido
CLOCK_S = 683.0                 # relogio de audio da captura nesse instante


def _cases(route, noise):
    """[(nome, ok, evidencia)] sobre as decisoes extraidas."""
    verdict = route['live_route_verdict']
    age_of = route['caption_age_s']
    is_noise = noise['is_noise_caption']
    out = []

    def check(name, ok, evidence):
        out.append((name, bool(ok), evidence))

    # A1 -- a idade
    live_fresh = {'type': 'caption', 'text': 'a', 'tap_ms': NOW_MS - 200.0}
    live_stale = {'type': 'caption', 'text': 'b', 'tap_ms': NOW_MS - 9000.0}
    a_fresh = age_of(live_fresh, now_ms=NOW_MS)
    a_stale = age_of(live_stale, now_ms=NOW_MS)
    check('A1 tap_ms: 200 ms de idade sao 0.2 s',
          a_fresh is not None and abs(a_fresh - 0.2) < 0.01, a_fresh)
    check('A1 tap_ms: 9 s de idade sao 9 s',
          a_stale is not None and abs(a_stale - 9.0) < 0.01, a_stale)
    stamped = {'end': 100.0, 'audio_age_s': 299.15}
    check('A1 audio_age_s do produtor e' + "'" + ' lido antes de qualquer estimativa',
          age_of(stamped, now_ms=NOW_MS) == 299.15, age_of(stamped, now_ms=NOW_MS))
    check('A1 end+relogio: a mesma conta quando o chamador passa o relogio',
          age_of({'end': 100.0}, now_ms=NOW_MS, clock_s=130.0) == 30.0,
          age_of({'end': 100.0}, now_ms=NOW_MS, clock_s=130.0))
    check('A1 sem fonte de idade e' + "'" + ' DESCONHECIDA, nunca zero',
          age_of({'text': 'sem relogio'}, now_ms=NOW_MS) is None,
          age_of({'text': 'sem relogio'}, now_ms=NOW_MS))
    # O RELOGIO PARA TRAS (achado do pai, 2026-11-11): `max(0.0, negativo)`
    # devolvia 0,0 s e o veredicto dizia `fresh`. O par que importa esta' aqui:
    # um carimbo no FUTURO e' idade DESCONHECIDA; um carimbo 0,1 s no PASSADO e'
    # mesmo fresco. So' o primeiro caso seria satisfeito por "tudo desconhecido".
    future = age_of({'tap_ms': NOW_MS + 5000.0}, now_ms=NOW_MS)
    check('A1 carimbo 5 s no FUTURO: idade DESCONHECIDA (nao "fresco")',
          future is None, future)
    recent = age_of({'tap_ms': NOW_MS - 100.0}, now_ms=NOW_MS)
    check('A1 carimbo 0,1 s no PASSADO: e' + "'" + ' fresco de verdade',
          recent is not None and abs(recent - 0.1) < 0.01, recent)
    check('A1 idade carimbada NEGATIVA tambem e' + "'" + ' desconhecida',
          age_of({'audio_age_s': -12.0}, now_ms=NOW_MS) is None,
          age_of({'audio_age_s': -12.0}, now_ms=NOW_MS))

    # A2 -- a rota
    v = verdict(live_fresh, now_ms=NOW_MS)
    check('A2 linha ao vivo fresca PINTA', v['paint'] and v['reason'] == 'fresh', v)
    v = verdict(live_stale, now_ms=NOW_MS)
    check('A2 linha ao vivo com 9 s RECUSA (stale)',
          (not v['paint']) and v['reason'] == 'stale' and v['age_s'] is not None and abs(v['age_s'] - 9.0) < 0.01, v)
    v = verdict({'route': 'redux-batch', 'text': 'lote', 'end': 383.84,
                 'audio_age_s': 299.15}, now_ms=NOW_MS)
    check('A2 linha de LOTE recusada por rota (batch-route), com a idade dita',
          (not v['paint']) and v['reason'] == 'batch-route'
          and v['producer'] == 'redux'
          and v['age_s'] is not None and abs(v['age_s'] - 299.15) < 0.01, v)
    v = verdict({'producer': 'redux', 'text': 'executor', 'start': 1.0,
                 'end': 2.0, 'audio_age_s': 12.0}, now_ms=NOW_MS)
    check('A2 o executor externo (producer=redux, sem route) e' + "'" + ' lote',
          (not v['paint']) and v['reason'] == 'batch-route', v)
    # O PAR MEDIDO PELO PAI (2026-11-11): 311 `CAPTION_WINDOW_BLANKED`, repintura
    # local em 0,11 s, 5 adocoes. O MESMO payload muda SO' o dono: com o player a
    # linha local cala; com o local ela PINTA. Uma arm so' com o caso `player`
    # seria satisfeita por "nunca pintar", e o par nao.
    pair = {'tap_ms': NOW_MS - 100.0,
            'text': 'It looks like we have our first.'}
    as_player = verdict(pair, now_ms=NOW_MS, route_owner='player')
    as_local = verdict(pair, now_ms=NOW_MS, route_owner='local')
    check('A2 PAR (mesmo payload, so o dono muda): player recusa, local PINTA',
          as_player['paint'] is False and as_player['reason'] == 'player-owns-route'
          and as_local['paint'] is True and as_local['reason'] == 'fresh',
          {'player': as_player, 'local': as_local})
    v = verdict({'tap_ms': NOW_MS - 100.0, 'text': 'Mmm Mmm Mmm.'}, now_ms=NOW_MS)
    check('A2 ouvinte de musica: o `Mmm` puro nao PINTA (noise)',
          (not v['paint']) and v['reason'] == 'noise', v)
    v = verdict({'tap_ms': NOW_MS - 100.0, 'text': 'Mmm, mas eu vou.'}, now_ms=NOW_MS)
    check('A2 e a MESMA linha com palavra real PINTA (nunca se cala a fala)',
          v['paint'] and v['reason'] == 'fresh', v)
    v = verdict(live_fresh, now_ms=NOW_MS, route_owner='player')
    check('A2 com o player como dono a linha local nao pinta (player-owns-route)',
          (not v['paint']) and v['reason'] == 'player-owns-route', v)
    v = verdict({'text': 'sem relogio'}, now_ms=NOW_MS)
    check('A2 idade desconhecida PINTA e o motivo e' + "'" + ' unknown-age',
          v['paint'] and v['reason'] == 'unknown-age' and v['age_s'] is None, v)
    v = verdict({'text': 'carimbo no futuro', 'tap_ms': NOW_MS + 5000.0}, now_ms=NOW_MS)
    check('A2 carimbo no futuro NAO vira "fresh": pinta como unknown-age',
          v['paint'] and v['reason'] == 'unknown-age', v)

    # A3 -- o ruido (a regra que ja' existe; este portao paga a regressao)
    check('A3 "Mmm Mmm Mmm." e' + "'" + ' ruido',
          is_noise('Mmm Mmm Mmm.'), is_noise('Mmm Mmm Mmm.'))
    check('A3 "Mhm," e' + "'" + ' ruido', is_noise('Mhm,'), is_noise('Mhm,'))
    check('A3 NUNCA uma linha com palavra real: "Mmm, mas eu vou." fica',
          not is_noise('Mmm, mas eu vou.'), is_noise('Mmm, mas eu vou.'))
    check('A3 a fala normal fica: "hello world" / "" / "Oh."',
          not is_noise('hello world') and not is_noise('') and not is_noise('Oh.'),
          [is_noise(t) for t in ('hello world', '', 'Oh.')])
    return out


def _admit_arms():
    """A4 -- o ponto unico como ele e' SHIPPED (modulo real, importado)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location('live_route_arm', ROUTE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    logs = []
    out = []

    def check(name, ok, evidence):
        out.append((name, bool(ok), evidence))

    mod.note_route_owner('local')
    now = NOW_MS
    fresh = mod.admit({'type': 'caption', 'text': 'fala', 'tap_ms': now - 100.0},
                      log=logs.append, now_ms=now)
    check('A4 admissao: a linha PINTA e leva age_s honesto',
          (not fresh.get('history_only')) and fresh.get('age_s') is not None
          and abs(fresh['age_s'] - 0.1) < 0.01,
          fresh)

    stale = {'type': 'caption', 'text': 'replay', 'tap_ms': now - 299000.0}
    once = mod.admit(dict(stale), log=logs.append, now_ms=now)
    twice = mod.admit(dict(stale), log=logs.append, now_ms=now)
    refused_lines = [x for x in logs if x.startswith('LIVE_ROUTE_REFUSED')]
    check('A4 recusa: history_only + route_refused + age_s (o texto NAO se perde)',
          once.get('history_only') is True and once.get('route_refused') == 'stale'
          and once.get('age_s') is not None and abs(once['age_s'] - 299.0) < 0.1
          and twice.get('history_only'),
          {'once': once.get('route_refused'), 'age': once.get('age_s')})
    check('A4 o log sai UMA vez por episodio (duas recusas, uma linha)',
          len(refused_lines) == 1, refused_lines)
    mod.admit({'type': 'caption', 'text': 'outra', 'tap_ms': now - 50.0},
              log=logs.append, now_ms=now)
    mod.admit(dict(stale), log=logs.append, now_ms=now)
    refused_lines = [x for x in logs if x.startswith('LIVE_ROUTE_REFUSED')]
    check('A4 pintar de novo ABRE um episodio novo (a 2a recusa e' + "'" + ' dita)',
          len(refused_lines) == 2, len(refused_lines))

    noise_line = mod.admit({'type': 'caption', 'text': 'Mmm.', 'tap_ms': now - 50.0},
                           log=logs.append, now_ms=now)
    check('A4 o `Mmm` do ouvinte vai para o historico e NAO pinta (route_refused=noise)',
          noise_line.get('history_only') is True
          and noise_line.get('route_refused') == 'noise'
          and noise_line.get('text') == 'Mmm.', noise_line)

    mod.note_route_owner('player')
    player = mod.admit({'type': 'caption', 'text': 'mic', 'tap_ms': now - 50.0},
                       log=logs.append, now_ms=now)
    check('A4 dono=player: a linha local vai para o historico, nao pinta',
          player.get('history_only') is True
          and player.get('route_refused') == 'player-owns-route', player.get('route_refused'))
    mod.note_route_owner('local')
    return out, logs


def _cost_arms(route, noise):
    """A5 -- o custo das decisoes, medido (o dono paga-o por legenda)."""
    verdict = route['live_route_verdict']
    payload = {'type': 'caption', 'text': 'uma linha de tamanho normal',
               'tap_ms': NOW_MS - 300.0}
    n = 2000
    t_route = timeit.timeit(lambda: verdict(payload, now_ms=NOW_MS), number=n) / n
    longest = ('the whole company, if you think about it, is the ultimate form of '
               'executive leadership and it never stops')
    t_noise = timeit.timeit(lambda: noise['is_noise_caption'](longest), number=n) / n
    return [('A5 custo: rota %.2f us e ruido %.2f us por legenda (< 5 us)'
             % (t_route * 1e6, t_noise * 1e6),
             t_route < 5e-6 and t_noise < 5e-6,
             {'route_us': round(t_route * 1e6, 2), 'noise_us': round(t_noise * 1e6, 2)})]


def _take_head_arms():
    """A6 -- o lote limitado: devolve o MAIS ANTIGO, na ordem, sem perder nada."""
    import importlib.util

    import numpy as np

    spec = importlib.util.spec_from_file_location('live_queue_arm', QUEUE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tmp = tempfile.mkdtemp(prefix='live-route-head-')
    try:
        pending = mod.PendingAudio(rate=16000, ram_s=1.0, spool_dir=tmp,
                                   sweep_stale=False)
        blocks = [np.full(1600, float(i), dtype='float32') for i in range(300)]
        for block in blocks:
            pending.add(block)             # 300 x 1600 = 30 s de audio
        before = pending.seconds()
        head, samples = pending.take_head(5 * 16000)
        first_vals = [float(b[0]) for b in head]
        second, second_samples = pending.take_head(5 * 16000)
        second_vals = [float(b[0]) for b in second]
        out = [
            ('A6 take_head devolve 5 s de 30 s', samples == 5 * 16000 and abs(before - 30.0) < 0.01,
             {'before_s': before, 'head_s': samples / 16000.0}),
            ('A6 o que sobra fica na fila (nada perdido)',
             abs(pending.seconds() - 20.0) < 0.01, pending.seconds()),
            ('A6 a ORDEM e' + "'" + ' a da chegada (o mais antigo primeiro)',
             first_vals == [float(i) for i in range(len(first_vals))]
             and second_vals == [float(i) for i in
                                 range(len(first_vals), len(first_vals) + len(second_vals))],
             {'first': first_vals[:3], 'second': second_vals[:3]}),
            ('A6 as duas metades somam os 10 s pedidos', second_samples == 5 * 16000,
             second_samples / 16000.0),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


# ── I1: o CHAMADOR REAL, importado e conduzido ───────────────────────────────
_LOAD_SEQ = [0]


def _load_worker(path):
    """O worker INTEIRO como modulo (0,03 s medidos), como o bridge o carrega."""
    # O worker faz `sys.path.insert(0, HERE)` e importa os irmaos; uma COPIA
    # mutada vive noutro diretorio, por isso o diretorio do worker tem de estar
    # no caminho primeiro (senao o mutante morre por `punctuation_model` antes de
    # chegar ao `emit` e a arm passava a apanhar a coisa errada).
    worker_dir = os.path.dirname(os.path.abspath(WORKER))
    if worker_dir not in sys.path:
        sys.path.insert(0, worker_dir)
    _LOAD_SEQ[0] += 1
    name = 'sotto_worker_emit_%d' % _LOAD_SEQ[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _drive_emit(path):
    """Um caption de cada porta pelo `emit` REAL. Devolve (linhas, stderr, exc)."""
    mod = _load_worker(path)
    buf, err = io.StringIO(), io.StringIO()
    real_out, real_err = sys.stdout, sys.stderr
    now_ms = time.time() * 1000.0
    raised = None
    sys.stdout, sys.stderr = buf, err
    try:
        mod.emit(type='caption', text='ola mundo', tap_ms=now_ms - 100.0)
        mod.emit(type='caption', text='linha de ha 9 s', tap_ms=now_ms - 9000.0)
        mod.emit(type='caption', text='Mmm.', tap_ms=now_ms - 100.0)
        mod.emit(type='caption', text='lote', route='redux-batch', end=10.0,
                 producer='redux')
        mod.emit(type='status', state='probe', stage='route')
    except BaseException as exc:                      # noqa: BLE001
        raised = exc
    finally:
        sys.stdout, sys.stderr = real_out, real_err
    lines = []
    for line in buf.getvalue().splitlines():
        if not line.strip():
            continue
        try:
            lines.append(json.loads(line))
        except ValueError:
            lines.append({'__unparsed__': line})
    return lines, err.getvalue(), raised


def _emit_arms(path=None):
    """As arms do chamador real. `path=None` = o worker da ARVORE."""
    path = path or WORKER
    lines, err, raised = _drive_emit(path)
    out = []

    def check(name, ok, evidence):
        out.append((name, bool(ok), evidence))

    check('I1 o `emit` REAL aceita 5 payloads sem excecao (o defeito `log=err` '
          'rebentava no 1o caption)',
          raised is None and len(lines) == 5,
          {'raised': repr(raised)[:200], 'lines': len(lines)})
    if raised is not None or len(lines) != 5:
        return out
    fresh, stale, noise, batch, status = lines
    check('I1 fresco PINTA: sem `history_only` e `age_s` honesto',
          fresh.get('history_only') is None and fresh.get('age_s') is not None
          and abs(fresh['age_s'] - 0.1) < 0.01, fresh)
    check('I1 as tres recusas marcam `history_only` com o motivo certo',
          [stale.get('route_refused'), noise.get('route_refused'),
           batch.get('route_refused')] == ['stale', 'noise', 'batch-route']
          and all(x.get('history_only') is True for x in (stale, noise, batch)),
          [stale.get('route_refused'), noise.get('route_refused'),
           batch.get('route_refused')])
    check('I1 a recusa e' + "'" + ' DITA no stderr e NAO polui o stdout',
          'LIVE_ROUTE_REFUSED reason=stale' in err
          and 'LIVE_ROUTE_REFUSED reason=noise' in err
          and 'LIVE_ROUTE' not in json.dumps(lines[0]), err.strip()[:120])
    check('I1 um payload que nao e' + "'" + ' caption atravessa intacto',
          status == {'type': 'status', 'state': 'probe', 'stage': 'route'}, status)
    return out


# ── W: as emendas (o guarda e' CHAMADO, nao so' escrito) ────────────────────
def _patch_added(path):
    """As linhas ADICIONADAS do patch, sem os `+` (o que a emenda escreve)."""
    if not os.path.isfile(path):
        return ''
    lines = []
    for line in _src(path).splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            lines.append(line[1:])
    return '\n'.join(lines)


def _wiring_arms():
    worker_src = _src(WORKER)
    switch_src = _src(SWITCH)
    queue_src = _src(QUEUE)
    shell_src = _src(SHELL) if os.path.isfile(SHELL) else ''
    worker_pending_src = _patch_added(WORKER_PATCH)
    shell_pending_src = _patch_added(SHELL_PATCH)
    out = []

    def where(tree_text, patch_text, needle):
        if needle in tree_text:
            return 'tree', False
        if needle in patch_text:
            return 'patch', True
        return '', False

    def check(name, located, pending, evidence):
        out.append((name, bool(located), {'at': located, 'pending': pending,
                                          'evidence': evidence}))

    # W1: o chamador esta' na ARVORE (o patch do worker foi aplicado em
    # `fb3206d`; um patch pendente deixou de ser desculpa, e a arm antiga ainda
    # lia o patch velho com `log=err` e passava -- verde sobre um artefacto morto).
    check('W1 `emit` passa TODO caption por live_route.admit (ponto unico)',
          'tree' if 'live_route.admit(payload, log=route_log)' in worker_src else '',
          False, 'sotto_worker.emit')

    # W1-bis: a chamada DENTRO de `emit` (AST, nao texto: os comentarios acima
    # citam `live_route.admit` e um grep dava verde sem invocador nenhum) e o
    # `log=` tem de ser um nome de MODULO. E' o defeito do `log=err`: `err` era
    # local do `except` e o primeiro caption levava UnboundLocalError.
    emit_log_name = None
    module_names = set()
    worker_tree = ast.parse(worker_src)
    for node in worker_tree.body:
        if isinstance(node, (ast.Assign, ast.FunctionDef, ast.AsyncFunctionDef)):
            targets = node.targets if isinstance(node, ast.Assign) else ()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                module_names.add(node.name)
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        module_names.add(sub.id)
    for node in ast.walk(worker_tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'emit':
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == 'admit'
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == 'live_route'):
                    for kw in sub.keywords:
                        if kw.arg == 'log' and isinstance(kw.value, ast.Name):
                            emit_log_name = kw.value.id
    check('W1-bis a chamada esta DENTRO de `emit` e o `log=` e' + "'" + ' um nome de MODULO',
          'ast' if emit_log_name and emit_log_name in module_names else '',
          False, {'log_name': emit_log_name})

    # W7: AS DUAS LINHAS TEM DE CHEGAR AO LOG DO MOTOR. `stderr_tail` so' e'
    # publicado na cauda da morte; a casa pagou isto em 2026-11-10
    # (`WORKER_BOOT_PROF` escrito e nunca lido). A arm le a LISTA por AST: os
    # comentarios da propria lista citam `LIVE_ROUTE_REFUSED` e
    # `LIVE_ROUTE_UNKNOWN_AGE`, logo um grep dava verde com a lista intacta.
    visible = set()
    if os.path.isfile(SHELL):
        for node in ast.walk(ast.parse(_src(SHELL))):
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == 'ENGINE_VISIBLE_TAGS'
                    for t in node.targets):
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        visible.add(sub.value)
    check('W7 as duas linhas da rota estao em ENGINE_VISIBLE_TAGS (senao morrem '
          'no stderr_tail)',
          'ast' if {'LIVE_ROUTE_REFUSED', 'LIVE_ROUTE_UNKNOWN_AGE'} <= visible else '',
          False, sorted(t for t in visible if t.startswith('LIVE_ROUTE')))

    # W2/W3 sao meus e estao na arvore.
    drain = ''
    for node in ast.walk(ast.parse(switch_src)):
        if isinstance(node, ast.FunctionDef) and node.name == 'drain_captions':
            drain = ast.dump(node)
    check('W2 `drain_captions` carimba `audio_age_s` (a idade que a rota le)',
          'tree' if 'audio_age_s' in drain else '', False, 'engine_switch.drain_captions')
    tick = ''
    for node in ast.walk(ast.parse(switch_src)):
        if isinstance(node, ast.FunctionDef) and node.name == 'tick':
            tick = ast.dump(node)
    check('W3 `tick` publica o dono decidido (`note_route_owner`) para a guarda',
          'tree' if 'note_route_owner' in tick else '', False, 'engine_switch.tick')
    check('W2-bis o carimbo do drain NAO transforma relogio para tras em "fresco"',
          'tree' if ('max(0.0, float(self._audio_clock_s)' not in switch_src
                     and 'else None)' in switch_src) else '', False,
          'engine_switch.drain_captions')
    check('W4 a passagem do lote e' + "'" + ' LIMITADA (`take_pending(max_s=...)`) e a '
          'fila sabe cortar a cabeca (`take_head`)',
          'tree' if ('take_pending(max_s=REDUX_BATCH_PASS_MAX_S)' in switch_src
                     and 'def take_head' in queue_src) else '', False,
          'engine_switch.flush_pending + live_queue.take_head')

    place, pending = where(shell_src, shell_pending_src,
                           'if self.external_owner_refuses(source):')
    check('W5 a pintura da shell testa a POSSE decidida (`external_owner_refuses`)',
          place, pending, 'sotto_webview.on_worker_caption')
    place, pending = where(shell_src, shell_pending_src,
                           "set_owner('local', reason=reason, had_line=had_line)")
    check('W6 a QUEDA de posse e' + "'" + ' dita SEMPRE (com `had_line`)',
          place, pending, 'sotto_webview._release')
    # W6-bis: "uma vez por TRANSICAO" -- o escritor unico tem de sair cedo quando
    # o dono nao muda, senao a posse fica a ser dita em cada linha (311
    # `CAPTION_WINDOW_BLANKED` na sessao: o log perder-se-ia em repeticao).
    transition = None
    for src in (shell_src, shell_pending_src):
        if src and 'if owner == previous:' in src and 'EXTERNAL_OWNER' in src:
            transition = 'tree' if src is shell_src else 'patch'
            break
    check('W6-bis a posse so' + "'" + ' e' + "'" + ' ESCRITA numa TRANSICAO '
          '(`owner == previous` sai cedo)', transition or '', pending,
          'sotto_webview.set_external_owner')
    return out


def _patched_text(rel_path, patch_path):
    """O ficheiro com o patch aplicado por `patch -p1`, num diretorio temporario.

    NAO se reconstroi o diff a' mao: a versao anterior fazia o AST julgar um
    ficheiro que o `git apply` nunca produziria (visto a 2026-11-11: o
    `on_worker_caption` saiu duplicado e o hunk seguinte aplicado por cima). O
    binario que aplica a emenda e' o mesmo que a aplica a serio.
    """
    if not os.path.isfile(patch_path):
        return ''
    rel = os.path.relpath(os.path.join(ROOT, *os.path.split(rel_path)), ROOT)
    tmp = tempfile.mkdtemp(prefix='live-route-patch-')
    try:
        dst = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, rel), dst)
        try:
            proc = subprocess.run(
                ['patch', '-p1', '--silent', '-d', tmp, '-i',
                 os.path.abspath(patch_path)],
                capture_output=True, text=True)
        except OSError as exc:
            print('NOTE `patch` indisponivel (%r): a emenda nao pode ser julgada '
                  'por AST, so' % exc)
            return ''
        if proc.returncode != 0:
            print('NOTE `patch` falhou (rc=%s): a emenda nao se aplica'
                  % proc.returncode)
            return ''
        with io.open(dst, encoding='utf-8') as fh:
            return fh.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _judge():
    route = _route_ns()
    noise = _noise_ns()
    checks = list(_cases(route, noise))
    checks += _cost_arms(route, noise)
    return checks


def _report(checks, title=''):
    passed = sum(1 for _n, ok, _e in checks if ok)
    for name, ok, evidence in checks:
        mark = 'PASS' if ok else 'FAIL'
        extra = ''
        if isinstance(evidence, dict) and evidence.get('pending'):
            extra = '  [pending:%s]' % (evidence.get('at') or '-')
        print('%s %s%s' % (mark, name, extra))
    print('%s%d/%d arms' % (title, passed, len(checks)))
    return passed == len(checks)


MUTANTS = [
    ('M1 a idade deixa de existir: `tap_ms` ignorado',
     'if isinstance(tap, (int, float)) and tap > 0:', 'if False:'),
    ('M2 a idade carimbada pelo produtor ignorada',
     'if isinstance(stamped, (int, float)):', 'if False:'),
    ('M3 nada e' + "'" + ' "velho": LIVE_MAX_AGE_S para o infinito',
     'LIVE_MAX_AGE_S = 2.5', 'LIVE_MAX_AGE_S = 1e9'),
    ('M4 o lote volta a pintar (a porta da rota aberta)',
     'if producer == BATCH_PRODUCER:', 'if False:'),
    ('M5 a posse do player deixa de ser respeitada',
     'if route_owner == OWNER_PLAYER:', 'if False:'),
    ('M6 o filtro de ruido fica vazio (nenhum `Mmm` recusado)',
     r'_NOISE_WORD = re.compile(r"(?:m+|hm+|mhm+)[.,!?…]*", re.IGNORECASE)',
     '_NOISE_WORD = re.compile(r"(?!)")'),
    ('M7 o relogio para tras volta a dizer "fresco" (max(0.0) fresco)',
     'if delta < limit:', 'if False:'),
    ('M8 a porta de ruido do ponto de pintura removida (o `Mmm` pinta outra vez)',
     'if _caption_is_noise(payload):', 'if False:'),
]


WIRING_MUTANTS = [
    ('M9 o `log=` da emenda volta a ser `err` (o defeito do commit fb3206d)',
     'log=route_log)', 'log=err)'),
]


def _neg_arm_wiring():
    """Muta o CHAMADOR numa copia do worker e exige o `emit` real a cair."""
    src = _src(WORKER)
    caught = 0
    tmp = tempfile.mkdtemp(prefix='live-route-emit-')
    try:
        for index, (label, old, new) in enumerate(WIRING_MUTANTS, start=1):
            if old not in src:
                print('M%d ANCORA NAO ENCONTRADA -- mutacao impossivel (%s)'
                      % (len(MUTANTS) + index, label))
                continue
            path = os.path.join(tmp, 'sotto_worker_m%d.py' % index)
            with io.open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(src.replace(old, new, 1))
            lines, _err, raised = _drive_emit(path)
            number = len(MUTANTS) + index
            if raised is not None or len(lines) != 5:
                caught += 1
                print('M%d CAUGHT [emit] by %r -- %s'
                      % (number, repr(raised)[:80] if raised else
                         'linhas=%d' % len(lines), label))
            else:
                print('M%d ** INERT ** -- %s' % (number, label))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return caught, len(WIRING_MUTANTS)


def _neg_arm():
    """Muta uma COPIA do fonte real e exige que a MESMA tabela fique vermelha."""
    route_src = _src(ROUTE)
    noise_src = _src(NOISE)
    caught = 0
    for index, (label, old, new) in enumerate(MUTANTS, start=1):
        if old in route_src:
            target, route_text, noise_text = 'route', route_src.replace(old, new, 1), noise_src
        elif old in noise_src:
            target, route_text, noise_text = 'noise', route_src, noise_src.replace(old, new, 1)
        else:
            print('M%d ANCORA NAO ENCONTRADA -- mutacao impossivel (%s)' % (index, label))
            continue
        try:
            route = _extract(route_text, ROUTE_NAMES)
            noise = _extract(noise_text, NOISE_NAMES)
        except Exception as exc:                        # noqa: BLE001
            print('M%d CAUGHT by extraction (%r) -- %s' % (index, exc, label))
            caught += 1
            continue
        broken = [name for name, ok, _e in _cases(route, noise) if not ok]
        if broken:
            caught += 1
            print('M%d CAUGHT [%s] by %s -- %s' % (index, target, ','.join(broken)[:150], label))
        else:
            print('M%d ** INERT ** -- %s' % (index, label))
    wiring_caught, wiring_total = _neg_arm_wiring()
    caught += wiring_caught
    total = len(MUTANTS) + wiring_total
    print('NEG-ARM: %s (%d/%d)' % ('PASS' if caught == total else 'FAIL',
                                   caught, total))
    return 1 if caught == total else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='live-route-oracle')
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta o fonte real e exige NEG-ARM: PASS (m/m), rc=1')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return _neg_arm()

    checks = _judge()
    admit_checks, logs = _admit_arms()
    checks += admit_checks
    checks += _take_head_arms()
    checks += _emit_arms()
    checks += _wiring_arms()
    ok = _report(checks)
    pending = [e for _n, _ok, e in checks
               if isinstance(e, dict) and e.get('pending')]
    if pending:
        patches = [os.path.relpath(p, ROOT) for p in (WORKER_PATCH, SHELL_PATCH)
                   if os.path.isfile(p)]
        print('NOTE %d arm(s) pending a patch still not in the tree: %s'
              % (len(pending), ' | '.join(patches) or '(nenhum patch em disco)'))
    print('VERDICT: %s (%d/%d)' % ('PASS' if ok else 'FAIL',
                                   sum(1 for _n, good, _e in checks if good),
                                   len(checks)))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
