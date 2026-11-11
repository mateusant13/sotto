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
  W1..W6       AS EMENDAS: onde a guarda e' CHAMADA. O `worker/sotto_worker.py` e
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
import io
import os
import shutil
import subprocess
import sys
import tempfile
import timeit

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

    place, pending = where(worker_src, worker_pending_src,
                           'payload = live_route.admit(payload, log=err)')
    check('W1 `emit` passa TODO caption por live_route.admit (ponto unico)', place,
          pending, 'sotto_worker.emit')

    # W1-bis: a guarda dentro do `emit` (AST, nao texto): a chamada tem de estar
    # na FUNCAO, senao um comentario/nome solto a fazia passar.
    in_emit = False
    for src in (worker_src, worker_pending_src):
        if not src:
            continue
        try:
            tree = ast.parse(_patched_text(WORKER, WORKER_PATCH)
                             if src is worker_pending_src else src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'emit':
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                            and sub.func.attr == 'admit'
                            and isinstance(sub.func.value, ast.Name)
                            and sub.func.value.id == 'live_route'):
                        in_emit = True
    check('W1-bis a chamada esta DENTRO de `emit` (AST)', 'ast' if in_emit else '',
          pending, {'in_emit': in_emit})

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
    print('NEG-ARM: %s (%d/%d)' % ('PASS' if caught == len(MUTANTS) else 'FAIL',
                                   caught, len(MUTANTS)))
    return 1 if caught == len(MUTANTS) else 0


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
    checks += _wiring_arms()
    ok = _report(checks)
    pending = [e for _n, _ok, e in checks
               if isinstance(e, dict) and e.get('pending')]
    if pending:
        print('NOTE %d arm(s) pending a patch: %d hunk(s) not in the tree yet '
              '(worker: %s | shell: %s)'
              % (len(pending), len(pending),
                 os.path.relpath(WORKER_PATCH, ROOT), os.path.relpath(SHELL_PATCH, ROOT)))
    print('VERDICT: %s (%d/%d)' % ('PASS' if ok else 'FAIL',
                                   sum(1 for _n, good, _e in checks if good),
                                   len(checks)))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
