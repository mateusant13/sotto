#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: A IDADE DO AUDIO QUE ESTA' NO ECRa -- o numero que o dono pediu, e o grito. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A IDADE DO AUDIO QUE ESTA' NO ECRa -- o numero que o dono pediu, e o grito.

ORDEM DO DONO (2026-11-03), verbatim: *"tu nao tem a porra de um teste ou log
que mostra a discrepancia entre audio detectado e display na tela? nao tem nada
que grita que o budget de ter mostrado ja passou do ponto?"*.

MEDIDO antes deste portao existir (log VIVO dele, pid 4992, 17:17:59-17:18:03):
cinco legendas diferentes entraram em 4 s e o painel publicou UMA linha com as
cinco encadeadas -- e nada no log dizia de que instante era aquele audio. O
`CAPTION_OVERLAY_LAG` media a FILA (0-300 ms) e a fila era o menor dos atrasos:
o audio que a linha descreve ja' podia ter acabado segundos antes. Sem `tap_ms`
nao havia como provar nem refutar "esta' atrasado".

O QUE ESTE ORACULO JULGA (o codigo REAL, nao uma copia da regra):

  1. `tap_ms` VIAJA -- o `LineFormer.push(wall=...)` publica o instante de
     parede do bloco, e um `push` sem `wall` mantem o conjunto de chaves de
     antes (o pin do `per-app-source-plumbing-oracle` continua valido).
  2. `CAPTION_IN` -- a chegada ao shell traz `start`/`end`/`final`/`tap_ms` e a
     idade ja' calculada.
  3. `CAPTION_PAINT_LAG` -- a pintura no ecra traz `audio_ms` (audio -> pixel),
     `queue_ms` (a fila) e o veredicto `over`.
  4. `CAPTION_BUDGET_BLOWN` -- estourar o orcamento tem uma linha propria; nao
     estourar NAO a tem.
  5. `CAPTION_LAG_STATS` -- a serie publica p50/p90/max e a contagem de estouros.
  6. `CAPTION_ARRIVAL_BLOWN` -- se o audio JA' chegava velho, o log diz que a
     metade culpada e' o worker/tap e nao o desenho.

`--neg-arm`: muta uma COPIA de `app/webview/sotto_webview.py` de duas formas --
(1) `CAPTION_BUDGET_MS` para 10**9 (nada estoura nunca), (2) sem `tap_ms=` no
`push_caption_to_window` (a idade do audio desaparece) -- e exige as arms
correspondentes a VERMELHO. Um portao cujo mutante passa nao mede nada.
"""
import ast
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
sys.path.insert(0, WEBVIEW)
sys.path.insert(0, os.path.join(ROOT, 'worker'))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeOverlay(object):
    """O overlay REAL recebe texto; aqui so' registamos o que ele recebeu."""

    def __init__(self):
        self.hwnd = 424242
        self.visible = False
        self.texts = []
        self.cues = []

    def set_work_area(self, *_a, **_k):
        return True

    def set_text(self, text, previous=None, instant=False, cue=None):
        self.texts.append(text)
        self.cues.append(cue)
        return True

    def show(self, on=True):
        self.visible = bool(on)
        return True


def make_shell(mod, lines, hold=False):
    """Um objecto com os METODOS REAIS do `SottoShell` ligados a ele.

    Os nomes sao os que o codigo vivo usa; o resto (janela, bridge, painel) nao
    entra no caminho que se quer medir. `log` e' substituido por um colector,
    porque a pergunta e' exactamente "o que e' que o log diz".
    """
    shell = types.SimpleNamespace()
    shell.caption_overlay = FakeOverlay()
    shell.bridge = None
    shell._caption_wanted = True
    shell._caption_window_shown = True
    shell.external_captions_active = False
    shell.external_suppressed = 0
    shell.captions = 0
    shell.last_caption_at = 0.0
    shell.pending_error = None
    shell._source_epoch = 0
    shell._overlay_pushes = 0
    shell._caption_painted = ''
    shell._caption_drain_posted = False
    shell._caption_drain_posted_at = 0.0
    shell._caption_pending = None
    shell._caption_pending_instant = False
    shell._caption_pending_cue = None
    shell._caption_pending_tap_ms = None
    shell.CAPTION_BUDGET_MS = mod.SottoShell.CAPTION_BUDGET_MS
    shell.CAPTION_HOLD_BAND_MS = mod.SottoShell.CAPTION_HOLD_BAND_MS
    shell._caption_ages = []
    shell._caption_lag_blown = 0
    shell.display = {'scaleFactor': 1.0}
    shell.work_area = lambda: (0, 0, 1920, 1080)
    shell.emit_async = lambda kind, payload: None
    shell.exec_js_post = lambda _js: True
    shell._arm_caption_idle_hide = lambda: None
    shell._reload_policy = types.SimpleNamespace(boundary=lambda **_k: None)
    # A pintura corre SINCRONA: medir o desenho nao pode depender de uma thread,
    # e o slot e' o mesmo (`_drain_caption_pending` le' e limpa).
    if hold:
        # A PINTURA EM VOO: o slot fica pendente e a arm drena-a a mao, que e'
        # exactamente o estado real entre a chegada e o pixel.
        shell._caption_paint_wake = lambda: None
    else:
        shell._caption_paint_wake = types.MethodType(
            lambda self_: mod.SottoShell._drain_caption_pending(self_), shell)
    for name in ('on_worker_caption', 'push_caption_to_window',
                 '_drain_caption_pending', '_caption_lag_note'):
        setattr(shell, name, types.MethodType(getattr(mod.SottoShell, name), shell))
    return shell


def make_log(sink):
    def _log(message, *_a, **_k):
        sink.append(str(message))
    return _log


def take(lines, needle, last=True):
    hits = [l for l in lines if needle in l]
    if not hits:
        return None
    return hits[-1] if last else hits[0]


def field(line, key):
    """`key=valor` de uma linha de log, como `float` quando for numero."""
    for token in (line or '').split():
        if token.startswith(key + '='):
            raw = token[len(key) + 1:]
            try:
                return float(raw)
            except ValueError:
                return raw
    return None


def arm_event_key(LineFormer):
    plain = LineFormer()
    before = plain.push('ola mundo', start=0.0, end=1.0)
    live = LineFormer(source='proc:4242')
    with_wall = live.push('ola mundo', start=0.0, end=1.0, wall=time.time())
    if not before or not with_wall:
        return False, 'o LineFormer nao devolveu evento'
    no_wall_keys = set(before[0])
    wall_keys = set(with_wall[0])
    ok = ('tap_ms' not in no_wall_keys
          and 'tap_ms' in wall_keys
          and no_wall_keys == {'type', 'text', 'start', 'end', 'final',
                               'closed', 'stable'})
    return ok, ('sem wall keys=%s | com wall tap_ms=%s'
                % (sorted(no_wall_keys), with_wall[0].get('tap_ms')))


def arm_arrival(mod, shell, lines, worker_event):
    now_ms = int(time.time() * 1000.0)
    meta = dict(worker_event)
    meta['tap_ms'] = now_ms - 3200
    shell.on_worker_caption('tres segundos de atraso', meta)
    incoming = take(lines, 'CAPTION_IN')
    blown = take(lines, 'CAPTION_ARRIVAL_BLOWN')
    ok = (incoming is not None and field(incoming, 'tap_ms') is not None
          and (field(incoming, 'age_ms') or 0) >= 3000 and blown is not None)
    return ok, ('CAPTION_IN=%s | BLOWN=%s'
                % ((incoming or 'AUSENTE')[:110], 'sim' if blown else 'AUSENTE'))


def arm_paint_on_time(mod, shell, lines, worker_event):
    lines[:] = []
    now_ms = int(time.time() * 1000.0)
    meta = dict(worker_event)
    meta['tap_ms'] = now_ms - 120
    shell.on_worker_caption('a tempo', meta)
    painted = take(lines, 'CAPTION_PAINT_LAG')
    blown = take(lines, 'CAPTION_BUDGET_BLOWN')
    got_tex = shell.caption_overlay.texts[-1:] == ['a tempo']
    ok = (painted is not None and 'over=false' in painted
          and blown is None and got_tex)
    return ok, ('PAINT_LAG=%s | BLOWN=%s | overlay=%r'
                % ((painted or 'AUSENTE')[:110], 'sim' if blown else 'nao',
                   shell.caption_overlay.texts[-1:]))


def arm_paint_late(mod, shell, lines, worker_event):
    lines[:] = []
    now_ms = int(time.time() * 1000.0)
    meta = dict(worker_event)
    meta['tap_ms'] = now_ms - 2400
    shell.on_worker_caption('fora do orcamento', meta)
    painted = take(lines, 'CAPTION_PAINT_LAG')
    blown = take(lines, 'CAPTION_BUDGET_BLOWN')
    ok = (painted is not None and 'over=true' in painted
          and blown is not None and (field(blown, 'audio_ms') or 0) >= 1500)
    return ok, ('PAINT_LAG=%s | BLOWN=%s'
                % ((painted or 'AUSENTE')[:110], (blown or 'AUSENTE')[:80]))


def arm_coalesce_keeps_both(mod, lines, worker_event):
    """Duas linhas DISTINTAS antes do pixel: nenhuma desaparece."""
    shell = make_shell(mod, lines, hold=True)
    now_ms = int(time.time() * 1000.0)
    first = dict(worker_event)
    first['tap_ms'] = now_ms - 300
    second = dict(worker_event)
    second['tap_ms'] = now_ms - 120
    lines[:] = []
    shell.on_worker_caption('primeira fala', first)
    shell.on_worker_caption('segunda fala', second)
    shell._drain_caption_pending()
    painted = take(lines, 'CAPTION_PAINT_LAG')
    coal = take(lines, 'CAPTION_COALESCE')
    text = (shell.caption_overlay.texts or [''])[-1]
    ok = (painted is not None and 'primeira fala' in text and 'segunda fala' in text
          and coal is not None and field(coal, 'coalesced') == 1)
    return ok, ('texto=%r | COALESCE=%s'
                % (text[:100], (coal or 'AUSENTE')[:80]))


def arm_coalesce_cumulative(mod, lines, worker_event):
    """A re-emissao CUMULATIVA da mesma linha nao se junta a ela mesma."""
    shell = make_shell(mod, lines, hold=True)
    lines[:] = []
    shell.on_worker_caption('a mesma linha', worker_event)
    shell.on_worker_caption('a mesma linha de novo', worker_event)
    shell._drain_caption_pending()
    text = (shell.caption_overlay.texts or [''])[-1]
    coal = take(lines, 'CAPTION_COALESCE')
    ok = text == 'a mesma linha de novo' and coal is None
    return ok, ('texto=%r | COALESCE=%s' % (text, 'sim' if coal else 'nao'))


def arm_init_declares_lag_fields(path=SHELL):
    """O CAMPO TEM DE EXISTIR ANTES DO PRIMEIRO USO (medido: 17:38:35).

    `BRIDGE_HANDLER_FAILED kind=caption-applied AttributeError: _caption_lag_blown`
    -- o primeiro ack estourava o orcamento antes de a serie existir, e a
    excepcao comia a linha do log no caso que interessa. Esta arm le o
    `__init__` do shell e exige as duas atribuicoes.
    """
    tree = ast.parse(io.open(path, encoding='utf-8').read())
    assigned = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '__init__':
            for inner in ast.walk(node):
                if isinstance(inner, ast.Assign):
                    for target in inner.targets:
                        if (isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == 'self'):
                            assigned.add(target.attr)
    missing = sorted({'_caption_ages', '_caption_lag_blown'} - assigned)
    return not missing, ('faltam=%s' % (missing or 'nenhum'))


def arm_tap_before_decode(path=WORKER):
    """O CARIMBO ANTES DO DECODE: sem isto a idade exclui a maior parcela.

    Medido 2026-11-03: `wall=time.time()` estava DEPOIS de `asr.run_chunk`, logo
    o `audio_ms` publicado no ecra excluia o AGC e o decode -- exactamente a
    pergunta do dono (*"tem 100% ctz que quando o audio e detectado ja tem x de
    tempo passado?"*). Esta arm le a ORDEM no AST: a atribuicao de `_wall_tap`
    tem de estar antes da chamada `run_chunk`, e o `wall=` do `former.push` tem
    de ser esse nome.
    """
    tree = ast.parse(io.open(path, encoding='utf-8').read())
    stamps = []
    decodes = []
    pushes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '_wall_tap':
                    stamps.append(node.lineno)
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, 'attr', getattr(func, 'id', ''))
            if name == 'run_chunk':
                decodes.append(node.lineno)
            if name == 'push':
                for kw in node.keywords:
                    if kw.arg == 'wall':
                        pushes.append((node.lineno, kw.value))
    # O `run_chunk` aparece noutras funcoes: o que conta e' o ULTIMO antes do
    # `push` que leva o carimbo, i.e. o mesmo laco.
    push_line, push_wall = (pushes[-1] if pushes else (None, None))
    before = [n for n in decodes if push_line and n < push_line]
    decode_line = max(before) if before else None
    stamp_line = max([n for n in stamps if push_line and n < push_line] or [None])
    wall_repr = ast.dump(push_wall) if push_wall is not None else 'AUSENTE'
    ok = (stamp_line is not None and decode_line is not None
          and stamp_line < decode_line
          and push_wall is not None
          and isinstance(push_wall, ast.Name) and push_wall.id == '_wall_tap')
    return ok, ('carimbo@%s decode@%s wall=%s'
                % (stamp_line, decode_line, wall_repr[:60]))


def arm_panel_apply_age(mod, lines):
    """O PIXEL DA PONTE: `_caption_applied` publica a idade do audio."""
    shell = make_shell(mod, lines)
    shell.caption_log = []
    shell._last_push_tap_ms = int(time.time() * 1000.0) - 2100
    shell._last_push_at = time.time() - 0.030
    handler = types.SimpleNamespace(_shell=shell)
    handler._caption_applied = types.MethodType(
        mod.SottoShell._caption_applied, handler) if hasattr(
            mod.SottoShell, '_caption_applied') else None
    if handler._caption_applied is None:
        # O metodo vive num handler, nao no shell: procura-o no modulo.
        for name in dir(mod):
            obj = getattr(mod, name)
            if isinstance(obj, type) and hasattr(obj, '_caption_applied'):
                handler._caption_applied = types.MethodType(
                    obj._caption_applied, handler)
                break
    lines[:] = []
    handler._caption_applied({'text': 'a linha no ecra'})
    applied = take(lines, 'CAPTION_APPLIED')
    blown = take(lines, 'CAPTION_BUDGET_BLOWN')
    ok = (applied is not None and 'over=true' in applied
          and field(applied, 'audio_ms') is not None
          and 'aged_kind=transport' in applied
          and blown is not None and 'path=panel' in blown)
    return ok, ('APPLIED=%s | BLOWN=%s'
                % ((applied or 'AUSENTE')[:120], (blown or 'AUSENTE')[:70]))


def arm_hold_band_named(mod, lines):
    """A ESPERA INTENCIONAL TEM NOME: `queue_ms` na banda de 1500 -> held.

    Medido 17:43:02/17:43:11/17:40:47 na sessao do dono: `queue_ms=1504`
    exatamente, tres vezes -- o `COMMIT_MAX_HOLD_MS` do painel a soltar a cauda
    depois de o audio parar. Sem o nome, o mesmo numero le-se como atraso.
    """
    shell = make_shell(mod, lines)
    shell.caption_log = []
    shell._last_push_tap_ms = int(time.time() * 1000.0) - 1560
    shell._last_push_at = time.time() - 1.504
    handler = types.SimpleNamespace(_shell=shell)
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and hasattr(obj, '_caption_applied'):
            handler._caption_applied = types.MethodType(obj._caption_applied, handler)
            break
    lines[:] = []
    handler._caption_applied({'text': 'a cauda segurada'})
    applied = take(lines, 'CAPTION_APPLIED')
    ok = (applied is not None and 'aged_kind=hold-expired' in applied
          and int(getattr(shell, '_caption_hold', 0)) == 1)
    return ok, (applied or 'AUSENTE')[:150]


def arm_stats(mod, shell, lines, worker_event):
    lines[:] = []
    now_ms = int(time.time() * 1000.0)
    for i in range(26):
        meta = dict(worker_event)
        meta['tap_ms'] = now_ms - (100 + i)
        shell.on_worker_caption('amostra %d' % i, meta)
    stats = take(lines, 'CAPTION_LAG_STATS')
    ok = (stats is not None and (field(stats, 'n') or 0) >= 25
          and field(stats, 'p50') is not None and field(stats, 'max') is not None
          and 'budget_ms=' in stats)
    return ok, (stats or 'AUSENTE')[:140]


def main(argv):
    neg = '--neg-arm' in argv
    worker = load_module(WORKER, 'sotto_worker_lag')
    shell_path = SHELL
    tmpdir = None
    if neg:
        # DUAS mutacoes, cada uma a derrubar UMA arm: o orcamento infinito e o
        # `tap_ms` que nao viaja. Sem as duas, um mutante que apague a instrucao
        # inteira passaria por uma arm que so' olha o texto do log.
        tmpdir = tempfile.mkdtemp(prefix='cap-lag-neg-')
        src = io.open(SHELL, encoding='utf-8').read()
        mut1 = src.replace('    CAPTION_BUDGET_MS = 1500',
                           '    CAPTION_BUDGET_MS = 10 ** 9', 1)
        mut2 = src.replace('self.push_caption_to_window(text, tap_ms=_tap)',
                           'self.push_caption_to_window(text)', 1)
        mut3 = src.replace("                text = _old + ' ' + text",
                           '                pass', 1)
        mut4 = src.replace("        tap = getattr(shell, '_last_push_tap_ms', None)",
                           '        tap = None', 1)
        mut6 = src.replace("        self._caption_lag_blown = 0",
                           '        pass', 1)
        mut7 = src.replace("    CAPTION_HOLD_BAND_MS = (1490, 1520)",
                           '    CAPTION_HOLD_BAND_MS = (0, 0)', 1)
        worker_src = io.open(WORKER, encoding='utf-8').read()
        mut5 = worker_src.replace('                    wall=_wall_tap,',
                                  '                    wall=time.time(),', 1)
        if (mut1 == src or mut2 == src or mut3 == src or mut4 == src
                or mut5 == worker_src or mut6 == src or mut7 == src):
            print('NEG-ARM IMPOSSIVEL: a ancora do mutante nao esta no shell')
            shutil.rmtree(tmpdir, ignore_errors=True)
            return 2
        shell_path = os.path.join(tmpdir, 'sotto_webview_m1.py')
        with io.open(shell_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(mut1)
        mut2_path = os.path.join(tmpdir, 'sotto_webview_m2.py')
        with io.open(mut2_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(mut2)
        mut3_path = os.path.join(tmpdir, 'sotto_webview_m3.py')
        with io.open(mut3_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(mut3)
        mut4_path = os.path.join(tmpdir, 'sotto_webview_m4.py')
        with io.open(mut4_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(mut4)
        mut7_path = os.path.join(tmpdir, 'sotto_webview_m7.py')
        with io.open(mut7_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(mut7)
        mut6_path = os.path.join(tmpdir, 'sotto_webview_m6.py')
        with io.open(mut6_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(mut6)
        mut5_path = os.path.join(tmpdir, 'sotto_worker_m5.py')
        with io.open(mut5_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(mut5)
    def run_arms(path, name):
        """Roda as cinco arms contra UM shell (o real, ou uma copia mutada)."""
        mod = load_module(path, name)
        sink = []
        real_log = mod.log
        mod.log = make_log(sink)
        lines = sink
        shell = make_shell(mod, lines)
        now_ms = int(time.time() * 1000.0)
        worker_event = {'start': 1.0, 'end': 2.0, 'final': False,
                        'stable': True, 'tap_ms': now_ms - 100}
        rows = []

        def arm(arm_name, ok, evidence):
            rows.append((arm_name, bool(ok), str(evidence)[:220]))
            print('%-28s %s %s' % (arm_name, 'PASS' if ok else 'RED',
                                   str(evidence)[:200]))

        try:
            for arm_name, fn in (
                    ('tap-ms-travels-on-the-event',
                     lambda: arm_event_key(worker.LineFormer)),
                    ('arrival-age-and-alarm',
                     lambda: arm_arrival(mod, shell, lines, worker_event)),
                    ('paint-lag-on-time',
                     lambda: arm_paint_on_time(mod, shell, lines, worker_event)),
                    ('paint-lag-blows-and-screams',
                     lambda: arm_paint_late(mod, shell, lines, worker_event)),
                    ('coalesce-keeps-both-lines',
                     lambda: arm_coalesce_keeps_both(mod, lines, worker_event)),
                    ('coalesce-cumulative-not-joined',
                     lambda: arm_coalesce_cumulative(mod, lines, worker_event)),
                    ('init-declares-lag-fields',
                     lambda: arm_init_declares_lag_fields()),
                    ('tap-stamped-before-decode',
                     lambda: arm_tap_before_decode()),
                    ('panel-apply-carries-audio-age',
                     lambda: arm_panel_apply_age(mod, lines)),
                    ('hold-band-is-named',
                     lambda: arm_hold_band_named(mod, lines)),
                    ('lag-stats-serie',
                     lambda: arm_stats(mod, shell, lines, worker_event))):
                ok, detail = fn()
                arm(arm_name, ok, detail)
        finally:
            mod.log = real_log
        return rows

    try:
        if neg:
            # O CONTRATO DA CASA: rc=1 = os mutantes foram apanhados. CADA
            # mutante tem de derrubar a SUA arm -- um mutante que nao derruba
            # nada e' uma instrucao que o portao nao mede.
            total = 0
            caught = 0
            for path, why, expect in (
                    (shell_path, 'CAPTION_BUDGET_MS=10**9',
                     {'arrival-age-and-alarm', 'paint-lag-blows-and-screams'}),
                    (mut2_path, 'push sem tap_ms',
                     {'paint-lag-on-time', 'paint-lag-blows-and-screams'}),
                    (mut3_path, 'sem juntar as falas',
                     {'coalesce-keeps-both-lines'}),
                    (mut4_path, 'pixel sem idade de audio',
                     {'panel-apply-carries-audio-age'}),
                    (mut5_path, 'carimbo depois do decode',
                     {'tap-stamped-before-decode'}),
                    (mut6_path, 'campo da serie nao declarado',
                     {'init-declares-lag-fields'}),
                    (mut7_path, 'banda do hold desligada',
                     {'hold-band-is-named'}),):
                print('=== mutante: %s' % why)
                if path in (mut5_path, mut6_path):
                    # O mutante do WORKER julga-se pela arm de AST, nao por um
                    # shell que nao existe neste ficheiro.
                    name = ('tap-stamped-before-decode' if path == mut5_path
                            else 'init-declares-lag-fields')
                    ok, detail = (arm_tap_before_decode(path)
                                  if path == mut5_path
                                  else arm_init_declares_lag_fields(path))
                    print('%-28s %s %s'
                          % (name, 'PASS' if ok else 'RED', detail[:200]))
                    rows = [(name, ok, detail)]
                else:
                    rows = run_arms(path, 'sotto_shell_lag_mutant')
                red = {n for n, ok, _ in rows if not ok}
                missed = expect - red
                total += 1
                if not missed:
                    caught += 1
                print('mutante %-26s %s (vermelhas: %s)'
                      % (why, 'APANHADO' if not missed else 'PASSOU',
                         ', '.join(sorted(red)) or 'nenhuma'))
            print('NEG-ARM: %s (%d/%d mutantes apanhados)'
                  % ('PASS' if caught == total else 'FAIL', caught, total))
            return 1 if caught == total else 0

        rows = run_arms(shell_path, 'sotto_shell_lag')
        bad = [n for n, ok, _ in rows if not ok]
        print('VERDICT: %s (%d/%d arms)'
              % ('PASS' if not bad else 'FAIL', len(rows) - len(bad), len(rows)))
        return 0 if not bad else 1
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
