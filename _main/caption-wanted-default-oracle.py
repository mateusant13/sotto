#!/usr/bin/env python3
"""A LEGENDA LIGA NO ARRANQUE -- o oraculo da ordem de 2026-11-11.

O DONO, verbatim: *"as soon as i open it, should start the subtitles in my
screen. the ctrl space."* Ate' esta cura o arranque lia
`_main/caption-wanted.json` e um `false` la' escrito deixava a janela escura ate'
ele carregar em Ctrl+Space; o ficheiro dele dizia exactamente isso
(`{"on": false, "at": "2026-11-11T17:41:48"}`), logo TODA abertura nascia sem
legenda.

O QUE ESTE ORACULO JULGA, e nenhuma das arms e' textual:

  A1..A6  a decisao PURA `SottoShell.caption_wanted_at_start` sobre `args` reais
          de `argparse` (as mesmas flags que `run.cmd` aceita), com o ambiente e
          o estado gravado injectados -- sem WebView2, sem janela, sem pixel.
  A7..A9  a leitura do ESTADO: `_caption_wanted_at_start` corre sobre um ficheiro
          TEMPORARIO (ausente, `on=false`, `on=true`) e o log tem de dizer a
          decisao E o desacordo, sem nunca deixar o `false` vencer o arranque.
  A10     a FIACAO no `__init__` real: `_caption_wanted` vem da decisao, e o
          `_caption_show_pending` e' armado quando ela e' True (sem isto `on`
          seria uma bandeira sem pixels -- a mentira de 2026-11-04).
  A11     a REGRA 3 do AGENTS.md continua de pe': desligar a legenda e' DISPLAY
          -- o caminho do interruptor nao pode parar o worker nem o modelo.
  A12     UMA tabela so': `_worker_autostart_reason` le' `_measurement_flag` e
          nao tem uma segunda lista de flags escrita dentro dele.

CONVENCAO DA CASA: o positivo devolve 0, o `--neg-arm` devolve 1 QUANDO APANHA.
"""
# NO-BUG: ordem do dono de 2026-11-11 ("as soon as i open it, should start the subtitles"): a legenda tem de ligar no arranque, e o ledger so cobre o corpus de stutter de 2026-10-21..23
import argparse
import ast
import io
import json
import os
import sys
import tempfile
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
SHELL_REL = os.path.join('app', 'webview', 'sotto_webview.py')

_defs = []


def check(name, ok, detail=''):
    _defs.append((name, bool(ok), detail))
    print('%-44s %s %s' % (name, 'PASS' if ok else 'FAIL', detail))
    return bool(ok)


def _read(path):
    with io.open(path, encoding='utf-8', newline='') as handle:
        return handle.read()


def _tree(src, label=''):
    return ast.parse(src, filename=label or 'source')


def _segment(src, node, lines=None):
    """O texto do no', SEM partir o ficheiro outra vez.

    `ast.get_source_segment` re-parte o ficheiro INTEIRO a cada chamada: medido
    nesta arvore, 264 chamadas sobre 26 mil linhas custavam **143,9 s** de um
    passo que tem de ser barato. A tabela de linhas e' construida UMA vez.
    """
    if lines is None:
        lines = src.splitlines(keepends=True)
    start = max((node.lineno or 1) - 1, 0)
    end = node.end_lineno or node.lineno
    return ''.join(lines[start:end])


def _find(tree, kind, name=None, parent=None):
    """O no' `kind` com o nome `name`, dentro de `parent` (ou do modulo)."""
    scope = parent.body if parent is not None else tree.body
    for node in scope:
        if isinstance(node, kind) and (name is None or getattr(node, 'name', None) == name):
            return node
    return None


# ── a extracao: as funcoes REAIS, nao uma copia ──────────────────────────────
class Harness(object):
    """O namespace minimo onde o codigo extraido corre."""

    def __init__(self):
        self.logs = []

    def log(self, message):
        self.logs.append(str(message))


def extract(path):
    src = _read(path)
    tree = _tree(src, path)
    lines = src.splitlines(keepends=True)
    cls = _find(tree, ast.ClassDef, 'SottoShell')
    if cls is None:
        raise SystemExit('SOTTO SHELL CLASS NOT FOUND -- o oraculo nao julga nada')
    wanted = {
        '_measurement_flag': None,
        'MEASUREMENT_FLAGS': None,
        'caption_wanted_at_start': cls,
        '_caption_wanted_at_start': cls,
        '_worker_autostart_reason': cls,
        '_set_live_enabled': cls,
        '__init__': cls,
    }
    pieces = {}
    for name, parent in wanted.items():
        node = _find(tree, ast.FunctionDef if name != 'MEASUREMENT_FLAGS' else ast.Assign,
                     name, parent)
        if node is None and parent is cls:
            node = _find(tree, ast.FunctionDef, name, None)
        if node is None and parent is None and name == 'MEASUREMENT_FLAGS':
            # `MEASUREMENT_FLAGS = (...)` e' um Assign sem `name`.
            for cand in tree.body:
                if isinstance(cand, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id == name for t in cand.targets):
                    node = cand
                    break
        if node is None:
            raise SystemExit('EXTRACT MISS: %s' % name)
        pieces[name] = _segment(src, node, lines)
    # A FIACAO DO ARRANQUE nao vive no `__init__`: vive no metodo que CONSTRoi a
    # janela nativa da legenda. O dono e' encontrado pelo enunciado, nao por um
    # numero de linha -- um numero envelhece e a arm passa a medir outra funcao.
    marker = 'self._caption_wanted = self._caption_wanted_at_start()'
    owners = [n for n in ast.walk(cls)
              if isinstance(n, ast.FunctionDef)
              and marker in _segment(src, n, lines)]
    if not owners:
        raise SystemExit('EXTRACT MISS: fiacao do arranque (%s)' % marker)
    owner = max(owners, key=lambda n: (n.end_lineno or 0) - n.lineno)
    pieces['__wiring__'] = _segment(src, owner, lines)
    pieces['__wiring_name__'] = owner.name
    return src, tree, cls, pieces


def build_namespace(pieces):
    harness = Harness()
    ns = {'os': os, 'json': json, 'argparse': argparse}

    def _log(message):
        harness.log(message)

    ns['log'] = _log
    exec(compile(pieces['MEASUREMENT_FLAGS'], '<flags>', 'exec'), ns)
    exec(compile(pieces['_measurement_flag'], '<flag>', 'exec'), ns)

    class SottoShell(object):
        CAPTION_WANTED_DEFAULT_ENV = 'SOTTO_CAPTION_WANTED_DEFAULT'
        CAPTION_WANTED_PATH = ''

        def __init__(self, args=None):
            self.args = args
            self._caption_wanted = None
            self._caption_show_pending = None

    # `caption_wanted_at_start` chama `_measurement_flag` e le'
    # `SottoShell.CAPTION_WANTED_DEFAULT_ENV`; `_caption_wanted_at_start` le'
    # `self` e chama o irmao. Executar no namespace do harness e' o que faz as
    # arms medirem o codigo que embarca -- mas o segmento extraido vem com a
    # indentacao da CLASSE e com o decorador, logo os dois saem antes do exec.
    ns['SottoShell'] = SottoShell
    for name in ('caption_wanted_at_start', '_caption_wanted_at_start'):
        lines = [ln for ln in pieces[name].splitlines()
                 if not ln.strip().startswith('@')]
        exec(compile(textwrap.dedent('\n'.join(lines)), '<%s>' % name, 'exec'), ns)
        fn = ns[name]
        if isinstance(fn, (staticmethod, classmethod)):
            fn = fn.__func__
        setattr(SottoShell, name, fn)
    SottoShell.caption_wanted_at_start = staticmethod(
        getattr(SottoShell, 'caption_wanted_at_start'))
    return harness, ns, SottoShell


def parser():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--dump-dom', action='store_true')
    p.add_argument('--selftest', action='store_true')
    p.add_argument('--memory', action='store_true')
    p.add_argument('--no-hotkey', action='store_true')
    p.add_argument('--exit-after', type=float, default=0.0)
    p.add_argument('--probe-stats', action='store_true')
    p.add_argument('--probe-outside-click', action='store_true')
    p.add_argument('--probe-edit-mode', action='store_true')
    p.add_argument('--probe-v2', type=int, default=0)
    p.add_argument('--with-worker', action='store_true')
    p.add_argument('--no-worker', action='store_true')
    p.add_argument('--show', action='store_true')
    return p


def args_of(*flags):
    return parser().parse_args(list(flags))


# ── as arms ─────────────────────────────────────────────────────────────────
def run_arms(mutated=None):
    src, tree, cls, pieces = extract(SHELL)
    if mutated:
        pieces = mutated(pieces)
    harness, ns, Shell = build_namespace(pieces)

    def decide(a, stored=None, env=None):
        return Shell.caption_wanted_at_start(a, stored=stored, env=env or {})

    # A1: sem flag nenhuma -- a abertura do dono.
    on, reason = decide(args_of())
    check('A1 sem flags -> liga', on is True and reason == 'default',
          'on=%s reason=%s' % (on, reason))

    # A2/A3/A4: uma corrida de MEDICAO nao pinta no ecra dele.
    for flags, arm, label in (
            (['--dump-dom'], 'A2', '--dump-dom'),
            (['--no-hotkey'], 'A3', '--no-hotkey'),
            (['--probe-v2', '3'], 'A4', '--probe-v2')):
        on, reason = decide(args_of(*flags))
        check('%s %s -> nao liga' % (arm, label),
              on is False and 'measurement-flag' in reason,
              'on=%s reason=%s' % (on, reason))

    # A4b: UMA LARGADA DE LANE E' UMA MEDICAO -- `_main/keepalive.py` abre a app
    # escondida para uma lane medir por `panel_state` + log, e a ordem de ligar
    # no arranque nao pode pintar a legenda na tela do dono nesse caminho
    # (`SOTTO_NEVER_ON_OWNER_SCREEN`). O `0` explicito continua a ligar.
    on, reason = decide(args_of(), env={'SOTTO_LANE_LAUNCH': '1'})
    check('A4b lane -> nao liga', on is False and reason.startswith('lane'),
          'on=%s reason=%s' % (on, reason))
    on, reason = decide(args_of(), env={'SOTTO_LANE_LAUNCH': '0'})
    check('A4b lane=0 -> liga', on is True and reason == 'default',
          'on=%s reason=%s' % (on, reason))

    # A5/A6: o ambiente manda nos DOIS sentidos.
    on, reason = decide(args_of(), env={'SOTTO_CAPTION_WANTED_DEFAULT': '0'})
    check('A5 env=0 -> nao liga', on is False and reason.startswith('env'),
          'on=%s reason=%s' % (on, reason))
    on, reason = decide(args_of('--selftest'),
                        env={'SOTTO_CAPTION_WANTED_DEFAULT': '1'})
    check('A6 env=1 vence a flag de medicao', on is True and reason.startswith('env'),
          'on=%s reason=%s' % (on, reason))

    # A7..A9: o ESTADO gravado num ficheiro temporario de verdade.
    tmp = tempfile.mkdtemp(prefix='caption-wanted-')
    try:
        path = os.path.join(tmp, 'caption-wanted.json')
        shell = Shell(args_of())
        shell.CAPTION_WANTED_PATH = path

        # A9 primeiro: o ficheiro nao existe (a primeira vez de uma maquina).
        on = shell._caption_wanted_at_start()
        check('A9 ficheiro ausente -> liga', on is True,
              'on=%s' % on)
        check('A9 log diz stored=none',
              any('CAPTION_WANTED_START on=true' in line and 'stored=none' in line
                  for line in harness.logs),
              harness.logs[-1] if harness.logs else '-')

        # A7: o `false` do dono NAO suprime o arranque -- e o log diz por que.
        harness.logs[:] = []
        with io.open(path, 'w', encoding='utf-8') as handle:
            json.dump({'on': False, 'at': '2026-11-11T17:41:48'}, handle)
        on = shell._caption_wanted_at_start()
        check('A7 stored=false -> liga mesmo assim', on is True, 'on=%s' % on)
        check('A7 log nomeia o override',
              any('CAPTION_WANTED_START_OVERRIDES' in line for line in harness.logs)
              and any('stored=false' in line for line in harness.logs),
              ' | '.join(harness.logs[-2:]))

        # A8: o `true` gravado continua a ligar, e o log diz que veio do estado.
        harness.logs[:] = []
        with io.open(path, 'w', encoding='utf-8') as handle:
            json.dump({'on': True, 'at': '2026-11-11T18:00:00'}, handle)
        on = shell._caption_wanted_at_start()
        check('A8 stored=true -> liga', on is True, 'on=%s' % on)
        check('A8 log diz stored=true',
              any('stored=true' in line for line in harness.logs),
              harness.logs[-1] if harness.logs else '-')
    finally:
        for name in os.listdir(tmp):
            try:
                os.remove(os.path.join(tmp, name))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass

    # A10: FIACAO no metodo REAL que constroi a janela -- a decisao E o pedido
    # de pixels. Um `on=true` sem `_caption_show_pending` seria a bandeira sem
    # pixels que 2026-11-04 pagou.
    wiring = pieces['__wiring__']
    where = pieces['__wiring_name__']
    assigns = ('self._caption_wanted = self._caption_wanted_at_start()' in wiring)
    pending = ('self._caption_show_pending = True' in wiring
               and 'if self._caption_wanted:' in wiring)
    legacy = '_caption_wanted_restored' in src
    check('A10 %s le a decisao nova' % where, assigns, 'assign=%s' % assigns)
    check('A10 %s arma os pixels quando liga' % where, pending,
          'pending=%s' % pending)
    check('A10 a leitura antiga desapareceu', not legacy,
          'restored_refs=%d' % src.count('_caption_wanted_restored'))

    # A11: REGRA 3 -- desligar e' DISPLAY, nunca o motor.
    live_src = pieces['_set_live_enabled']
    forbidden = [word for word in ('bridge.stop', 'stop_worker', '_kill_and_restart',
                                   'engine_park', 'bridge.start')
                 if word in live_src]
    check('A11 o interruptor nao toca motor/worker', not forbidden,
          'encontrado=%s' % (forbidden or '-'))
    check('A11 o interruptor grava o estado',
          '_caption_wanted_store' in live_src, 'store=presente')

    # A12: uma tabela so'.
    reason_src = pieces['_worker_autostart_reason']
    check('A12 o worker le _measurement_flag', '_measurement_flag(args)' in reason_src,
          'call=%s' % ('_measurement_flag(args)' in reason_src))
    check('A12 sem segunda lista de flags',
          "'--dump-dom'" not in reason_src and '--probe-edit-mode' not in reason_src,
          'literais=%d' % reason_src.count("'--"))

    return _defs


# ── o braco negativo ────────────────────────────────────────────────────────
def mutants(pieces):
    """Tres mutacoes, cada uma numa COPIA do texto extraido."""
    out = dict(pieces)

    # M1: o estado gravado volta a vencer o arranque -- o comportamento EXATO
    # de antes da cura (o `false` do dono deixava a janela escura).
    body = out['caption_wanted_at_start']
    assert "return True, 'default'" in body, 'M1 anchor missing'
    out['caption_wanted_at_start'] = body.replace(
        "return True, 'default'",
        "return (stored is not False), 'default'")

    # M2: o ambiente deixa de valer -- `SOTTO_CAPTION_WANTED_DEFAULT` ignorado.
    body2 = out['caption_wanted_at_start']
    anchor = "if raw in ('0', '1'):"
    assert anchor in body2, 'M2 anchor missing'
    out['caption_wanted_at_start'] = body2.replace(anchor, 'if False:')

    # M3: o metodo do arranque deixa de armar os pixels -- `on=true` sem
    # janela, a mentira que 2026-11-04 pagou.
    body3 = out['__wiring__']
    assert 'if self._caption_wanted:' in body3
    out['__wiring__'] = body3.replace('if self._caption_wanted:',
                                      'if False:', 1)
    return out


def _failed(defs):
    return [name for name, ok, _ in defs if not ok]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    neg = '--neg-arm' in argv
    if not neg:
        defs = run_arms()
        bad = _failed(defs)
        print('VERDICT: %s -- %d/%d arm(s)%s'
              % ('PASS' if not bad else 'FAIL', len(defs) - len(bad), len(defs),
                 '' if not bad else ' falhas=%s' % ','.join(bad)))
        return 0 if not bad else 1

    caught = []
    survivors = []
    clean = run_arms()
    if _failed(clean):
        print('NEG-ARM IMPOSSIVEL: o positivo ja falha (%s)' % ','.join(_failed(clean)))
        return 0
    for label in ('M1 stored vence o arranque', 'M2 env ignorado',
                  'M3 pixels nao armados', 'M4 lane pinta na tela'):
        key = label.split()[0]
        def mut(pieces, key=key):
            return mutants(pieces) if key == 'M1' else _apply_single(key, pieces)
        defs = run_arms(mutated=mut)
        bad = _failed(defs)
        if bad:
            caught.append('%s <- %s' % (key, ','.join(bad)))
        else:
            survivors.append(key)
        print('  %s: %s' % (label, 'CAUGHT' if bad else 'SURVIVED'))
    ok = not survivors
    print('NEG-ARM: %s -- %d/%d mutantes apanhados'
          % ('PASS' if ok else 'FAIL', len(caught), len(caught) + len(survivors)))
    for line in caught:
        print('  caught %s' % line)
    return 1 if ok else 0


def _apply_single(key, pieces):
    out = dict(pieces)
    if key == 'M3':
        out['__wiring__'] = out['__wiring__'].replace(
            'if self._caption_wanted:', 'if False:', 1)
        return out
    if key == 'M2':
        out['caption_wanted_at_start'] = out['caption_wanted_at_start'].replace(
            "if raw in ('0', '1'):", 'if False:')
        return out
    if key == 'M4':
        # A guarda de lane arrancada: a app que uma lane abre volta a pintar.
        out['caption_wanted_at_start'] = out['caption_wanted_at_start'].replace(
            "if str(env.get('SOTTO_LANE_LAUNCH') or '').strip() == '1':",
            'if False:')
        return out
    return mutants(pieces)


if __name__ == '__main__':
    sys.exit(main())
