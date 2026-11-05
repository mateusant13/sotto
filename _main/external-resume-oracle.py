#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# BLOCKS: BUG-20261023-03
"""EXTERNAL-RESUME ORACLE -- o ciclo de vida do worker quando a legenda externa acaba.

A ORDEM 3 do dono: *"legenda ao vivo, com o modelo nemotron... qualquer legenda que
ja passou tem que ser processada tambem pelo parakeet, ou imediatamente, ou com
delay, ou quando seguro de fazer isso... se minha legenda ao vivo ta desativada e
eu nao to usando, e so o parakeet que comanda."*

O CONTRATO MUDOU A 2026-11-03, por ordem do dono, verbatim: *"tu nao consegue
fazer o sotto se conectar ao audio atual inves de ficar matando o audio toda
hora?"*. Ate' aqui o estacionamento por causa das legendas do player era um
`bridge.stop('external-captions')`: MATAVA o processo, e com ele o cliente WASAPI
-- o audio do dono piscava a cada paragem -- e a volta custava uma carga de modelo
de 14-26 s. O log dele conta o custo: **15** `EXTERNAL_CAPTIONS_WORKER_PARKED` num
dia.

AGORA o estacionamento e' um PEDIDO NUM FICHEIRO (`park` no
`panel-visibility.json`, a mesma chave additive do `shed`): o worker LARGA O
MOTOR e MANTEM o processo e a captura. Um processo, um cliente de audio, nenhum
blink -- e nenhuma recarga quando o player volta.

Este portao prova as duas metades, e cada uma tem um mutante:

  E1-E5  o RELEASE so' limpa o pedido atras das mesmas quatro guardas, e NUNCA
         arranca um processo (o worker nunca saiu);
  E6-E8  o PARK publica `captions` e NAO chama `bridge.stop`; repetir o pedido
         nao republica; e a volta devolve o pedido a `None`.

O PISO DE 45 s SAIU. Ele existia porque cada disparo custava uma carga de modelo;
limpar um pedido nao custa nada, e manten-lo era o unico defeito que sobrava --
com ele o motor ficava largado ate' 45 s depois de o player parar.

    python _main\\external-resume-oracle.py            # rc=0 verde, rc=2 vermelho
    python _main\\external-resume-oracle.py --neg-arm  # rc=1 POR DESENHO

NAO lanca nada: importa a shell em processo, monta um `self` falso com os
atributos que os metodos leem, e conta as chamadas em vez de as fazer.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')
PREFIX = '_extresume-neg-'


def _read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def load_module(path, name):
    import importlib.util
    if os.path.dirname(path) not in sys.path:
        sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_mutant(text, name, old, new):
    if text.count(old) != 1:
        raise RuntimeError('ancora do mutante %r encontrada %d vez(es)'
                           % (name, text.count(old)))
    path = os.path.join(os.path.dirname(SHELL), PREFIX + name + '.py')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text.replace(old, new))
    return path


def clean_mutants():
    d = os.path.dirname(SHELL)
    for name in os.listdir(d):
        if name.startswith(PREFIX):
            try:
                os.remove(os.path.join(d, name))
            except OSError:
                pass


class _Exit(object):
    def __init__(self, v):
        self.v = v

    def is_set(self):
        return self.v


class _Child(object):
    pid = 4242


class _Bridge(object):
    """O que o estacionamento le' da ponte -- e o `stop` que ele NAO pode chamar."""

    def __init__(self):
        self.child = _Child()
        self.stops = []

    def stop(self, reason):
        self.stops.append(reason)
        self.child = None
        return True


def _stub(mod, **kw):
    s = type('Stub', (), {})()
    s.exiting = _Exit(kw.get('exiting', False))
    s._external_parked = kw.get('parked', True)
    s._paused = kw.get('paused', False)
    s.visible = kw.get('visible', True)
    s._caption_window_shown = kw.get('caption', False)
    s._engine_park = kw.get('engine_park', 'captions')
    s._last_external_resume = kw.get('last', 0.0)
    s.bridge = kw.get('bridge', None)
    s.starts = []
    s.parks = []
    s.publishes = []
    s.start_worker = lambda reason: (s.starts.append(reason), True)[1]
    s.engine_park_reason = lambda: getattr(s, '_engine_park', None)
    s.set_engine_park = lambda reason: (s.parks.append(reason),
                                        setattr(s, '_engine_park', reason),
                                        True)[2]
    s.publish_panel_visibility = lambda reason: (s.publishes.append(reason),
                                                 True)[1]
    return s


def arms(mod, text):
    """[(rotulo, ok, detalhe)] -- cada braco julga UMA coisa."""
    release = mod.SottoShell.on_external_captions_released
    park = mod.SottoShell._park_worker_for_external
    seen = []
    mod.log = lambda m: seen.append(m)
    out = []

    s = _stub(mod, exiting=True)
    r = release(s)
    out.append(('E1 shell a sair nao limpa o pedido', r is False and not s.parks,
                {'ret': r, 'parks': s.parks, 'log': seen[-1:]}))
    seen[:] = []

    s = _stub(mod, parked=False)
    r = release(s)
    out.append(('E2 release sem park nao limpa nada', r is False and not s.parks,
                {'ret': r, 'parks': s.parks}))
    seen[:] = []

    s = _stub(mod, paused=True)
    r = release(s)
    out.append(('E3 em pausa nao limpa o pedido', r is False and not s.parks,
                {'ret': r, 'parks': s.parks}))
    seen[:] = []

    s = _stub(mod, visible=False, caption=False)
    r = release(s)
    out.append(('E4 escondido nao limpa o pedido', r is False and not s.parks,
                {'ret': r, 'parks': s.parks}))
    seen[:] = []

    s = _stub(mod, visible=False, caption=True)
    r = release(s)
    out.append(('E5 a legenda visivel limpa o pedido e NAO arranca processo',
                r is True and s.parks == [None] and s.starts == [],
                {'ret': r, 'parks': s.parks, 'starts': s.starts}))
    seen[:] = []

    s = _stub(mod, parked=False, bridge=_Bridge())
    r = park(s, 'external:youtube:track')
    out.append(('E6 o park publica `captions` e NAO mata o processo',
                r is True and s.parks == ['captions'] and s.bridge.stops == []
                and getattr(s.bridge, 'child', None) is not None,
                {'ret': r, 'parks': s.parks, 'stops': s.bridge.stops}))
    seen[:] = []

    s = _stub(mod, parked=True, bridge=_Bridge())
    r = park(s, 'external:youtube:track')
    out.append(('E7 repetir o park nao republica', r is False and not s.parks,
                {'ret': r, 'parks': s.parks}))
    seen[:] = []

    s = _stub(mod, visible=True, engine_park='captions')
    r = release(s)
    out.append(('E8 a volta devolve o pedido a None (o motor recarrega)',
                r is True and s.parks == [None]
                and getattr(s, '_engine_park', 'x') is None,
                {'ret': r, 'parks': s.parks, 'park': s._engine_park}))
    seen[:] = []

    # PRECEDENCIA: os dois motivos dividem o mesmo campo, e quem liberta tem de
    # ser o SEU. Uma release de legendas nao devolve a GPU que outro app pediu.
    s = _stub(mod, visible=True, engine_park='vram')
    r = release(s)
    out.append(('E9 release de legendas nao liberta um park de VRAM',
                r is True and s.parks == [],
                {'ret': r, 'parks': s.parks, 'park': s._engine_park}))
    seen[:] = []

    # O CANAL INTEIRO, PONTA A PONTA: a shell ESCREVE o pedido no ficheiro real
    # (o `PanelVisibilityWriter` verdadeiro) e o LEITOR verdadeiro do worker
    # le'-o. Sem esta arm, "o pedido viaja" era uma afirmacao sobre dois nomes de
    # chave que ninguem tinha visto concordar.
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix='extresume-park-')
    path = os.path.join(tmpdir, 'panel-visibility.json')
    w = mod.PanelVisibilityWriter(path=path, observe=lambda: False,
                                  log=lambda _m: None, interval_s=30.0,
                                  park_provider=lambda: 'captions')
    w.write('test')
    sw_mod = load_module(os.path.join(REPO, 'worker', 'engine_switch.py'),
                         'extresume_switch')
    reader = sw_mod.PanelVisibilityReader(path)
    reader.read()
    out.append(('E11 o ficheiro real leva `park=captions` ate ao leitor do worker',
                reader.park() == 'captions' and reader.shed() == 'leve',
                {'park': reader.park(), 'shed': reader.shed()}))
    seen[:] = []

    resume = mod.SottoShell.resume_after_vram
    s = _stub(mod, visible=True, engine_park='captions')
    s._vram_parked = True
    r = resume(s, 9000.0)
    out.append(('E10 a GPU livre nao liberta um park de legendas',
                r is True and s.parks == [],
                {'ret': r, 'parks': s.parks, 'park': s._engine_park}))

    # O ESTADO TERMINAL QUE O DONO VIVEU (2026-11-05, medido na instancia viva):
    # `park='vram'` no ficheiro com 2826 MB LIVRES, `VRAM_GUARD_RESUMING` zero
    # vezes no log, `_vram_parked` ja' a False -- porque a saida por
    # "escondido" acontecia ANTES de levantar o pedido. O guarda nunca mais
    # tentava (a condicao do `elif` era `_vram_parked`) e o motor ficava largado
    # ate' ao reinicio: zero legendas as 18:09 em diante.
    seen[:] = []
    s = _stub(mod, visible=False, engine_park='vram')
    s._vram_parked = True
    r = resume(s, 2826.0)
    out.append(('E12 a GPU livre LEVANTA o pedido mesmo com o painel escondido',
                r is False and s.parks == [None]
                and getattr(s, '_engine_park', 'x') is None
                and s._vram_parked is False,
                {'ret': r, 'parks': s.parks, 'park': s._engine_park,
                 'vram_parked': s._vram_parked}))
    seen[:] = []
    # E13 -- o estado terminal e' IMPOSSIVEL: depois de libertar, uma segunda
    # passagem nao pode republicar nada (o pedido ja' esta' a None) e o parque
    # nao pode voltar sozinho.
    s = _stub(mod, visible=False, engine_park='vram')
    s._vram_parked = True
    resume(s, 2826.0)
    again = resume(s, 2826.0)
    out.append(('E13 um pedido levantado nao ressuscita',
                again is False and s.parks == [None]
                and getattr(s, '_engine_park', 'x') is None,
                {'second_ret': again, 'parks': s.parks,
                 'park': s._engine_park}))
    # E14-E16 -- A ESTEIRA DO PARQUE (medida 2026-11-05 18:46-18:48 no log do
    # dono: PARKING 635 -> RESUMING 2921 -> PARKING 901 -> RESUMING 2911, tres
    # voltas em seis minutos, cada volta uma carga de modelo de 54 s). O dip da
    # carga nao pode contar como "outra app quer a GPU" -- o predicado e' puro e
    # o relogio entra por parametro, por isso o oraculo conduz os dois lados sem
    # esperar 90 s.
    guard_cls = getattr(mod, 'VramGuard', None)
    out.append(('E0 a classe do guarda de VRAM existe', guard_cls is not None, {}))
    if guard_cls is not None:
        g = guard_cls.__new__(guard_cls)
        g._resumed_at = 1000.0
        r14 = g.allow_park(now=1010.0)
        out.append(('E14 dentro da graca pos-resume NAO parqueia',
                    r14 is False, {'allow': r14}))
        r15 = g.allow_park(now=1000.0 + guard_cls.POST_RESUME_GRACE_S + 1.0)
        out.append(('E15 passada a graca volta a poder parquear',
                    r15 is True, {'allow': r15}))
        g._resumed_at = 0.0
        r16 = g.allow_park(now=1010.0)
        out.append(('E16 sem resume nenhum o guarda continua a servir outra app',
                    r16 is True, {'allow': r16}))
        # FIACAO: o predicado tem de ser CONSULTADO pelo laco, senao as arms
        # E14-E16 medem uma funcao que ninguem chama.
        wired = 'if not self.allow_park():' in (text or '')
        out.append(('E17 o laco do guarda consulta a graca antes de parquear',
                    wired, {'wired': wired}))
    return out


MUTANTS = [
    ('sem-graca-pos-resume',
     'o dip da carga volta a contar como outra app e a esteira recomeca (E14)',
     """        return (now - self._resumed_at) >= self.POST_RESUME_GRACE_S""",
     """        return True""",
     'E14 dentro da graca pos-resume NAO parqueia'),
    ('graca-nao-ligada-ao-parque',
     'o predicado existe mas o laco do guarda nao o consulta (E17)',
     """                        if not self.allow_park():""",
     """                        if False:""",
     'E17 o laco do guarda consulta a graca antes de parquear'),
    ('sem-guarda-exiting',
     'a shell a morrer limpa o pedido enquanto o processo morre (E1)',
     """        if self.exiting.is_set():
            log('EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting')
            return False""",
     """        if False:
            log('EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting')
            return False""",
     'E1 shell a sair nao limpa o pedido'),
    ('sem-guarda-park',
     'um release sem park limpa um pedido que nao existe (E2)',
     """        if not self._external_parked:
            return False""",
     """        if False:
            return False""",
     'E2 release sem park nao limpa nada'),
    ('sem-guarda-pausa',
     'em pausa limpa o pedido (E3)',
     """        if self._paused:
            return False""",
     """        if False:
            return False""",
     'E3 em pausa nao limpa o pedido'),
    ('sem-guarda-visivel',
     'escondido limpa o pedido (E4)',
     """        if not (self.visible or getattr(self, '_caption_window_shown', False)):
            return False""",
     """        if False:
            return False""",
     'E4 escondido nao limpa o pedido'),
    ('legenda-nao-conta',
     'a legenda visivel deixa de contar (E5)',
     """        if not (self.visible or getattr(self, '_caption_window_shown', False)):
            return False""",
     """        if not self.visible:
            return False""",
     'E5 a legenda visivel limpa o pedido e NAO arranca processo'),
    ('park-mata-o-processo',
     'o park volta a MATAR o worker -- o blink e a recarga de antes (E6)',
     """        self._external_parked = True
        self.set_engine_park('captions')""",
     """        self._external_parked = True
        bridge.stop('external-captions')
        self.bridge = None""",
     'E6 o park publica `captions` e NAO mata o processo'),
    ('resume-escondido-nao-levanta',
     'a volta por GPU livre sai antes de levantar o pedido (E12, o estado terminal)',
     """        self._vram_parked = False
        showing = bool(self.visible or getattr(self, '_caption_window_shown', False))""",
     """        self._vram_parked = False
        if not (self.visible or getattr(self, '_caption_window_shown', False)):
            return False
        showing = bool(self.visible or getattr(self, '_caption_window_shown', False))""",
     'E12 a GPU livre LEVANTA o pedido mesmo com o painel escondido'),
]


def _run(mod, text=None):
    # O TEXTO E' O DA ARVORE QUE SE ESTA' A JULGAR. No braco negativo e' o do
    # MUTANTE: as arms de fiacao (`E17`) leem o fonte, e ler o original enquanto
    # se corre o mutante faria delas arms que nunca podem cair.
    return {label.split()[0]: (ok, got)
            for label, ok, got in arms(mod, text if text is not None else _read(SHELL))}


def neg_arm():
    text = _read(SHELL)
    caught = 0
    for name, why, old, new, arm in MUTANTS:
        try:
            path = build_mutant(text, name, old, new)
            mmod = load_module(path, 'extresume_%s' % name.replace('-', '_'))
            got = _run(mmod, _read(path))
            ok = got.get(arm.split()[0], (False, None))[0]
        except Exception as exc:  # noqa: BLE001
            ok, exc = False, exc
        finally:
            clean_mutants()
        if not ok:
            print('NEG-ARM %-26s RED as expected (%s)' % (name, why))
            caught += 1
        else:
            print('NEG-ARM %-26s ** INERT ** (%s)' % (name, why))
    print('NEG-ARM %d of %d mutant(s) caught' % (caught, len(MUTANTS)))
    if caught == len(MUTANTS):
        print('NEG-ARM PASS')
        return 1
    print('VERDICT: FAIL -- %d mutante(s) passaram' % (len(MUTANTS) - caught))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true',
                    help='os mutantes tem de derrubar O SEU braco')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    if args.neg_arm:
        return neg_arm()
    mod = load_module(SHELL, 'extresume_real')
    results = arms(mod, _read(SHELL))
    bad = 0
    for label, ok, got in results:
        print('%s %s  %s' % ('GREEN' if ok else 'RED  ', label,
                             '' if ok else got))
        bad += 0 if ok else 1
    print('bracos: %d verdes, %d vermelhos' % (len(results) - bad, bad))
    print('EXTERNAL-RESUME VERDICT %s' % ('PASS' if not bad else 'FAIL'))
    return 0 if not bad else 2


if __name__ == '__main__':
    sys.exit(main())
