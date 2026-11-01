#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# BLOCKS: BUG-20261023-03
"""EXTERNAL-RESUME ORACLE -- o ciclo de vida do worker quando a legenda externa acaba.

A ORDEM 3 do dono: *"legenda ao vivo, com o modelo nemotron... qualquer legenda que
ja passou tem que ser processada tambem pelo parakeet, ou imediatamente, ou com
delay, ou quando seguro de fazer isso... se minha legenda ao vivo ta desativada e
eu nao to usando, e so o parakeet que comanda."* O `AGENTS.md` fechava-a com um
buraco declarado: *"`on_external_captions_released()` nao traz o worker de volta
(de proposito...)"*.

RE-MEDIDO 2026-10-23: **o buraco, como estava escrito, ja nao existe.** O metodo
(mesma revisao, `SottoShell.on_external_captions_released`) traz o worker de
volta, atras de QUATRO guardas e de um piso de 45 s:

  exiting        a shell esta a morrer -> nao arranca (senao fica um ORFAO: o
                 `os._exit` nao mata o filho, e um worker orfao carrega 1,2 GB
                 depois de a app ter fechado -- medido 2026-10-20)
  !parked        um release sem park e ruido do leitor
  paused         o dono pos o Sotto em pausa
  escondido      nem painel nem legenda visiveis -> nao ha para quem transcrever
  piso 45 s      o gatilho e um elemento de UI (o leitor faz poll a 0,30 s), nao
                 audio: um player que pestaneja a legenda custaria uma carga de
                 modelo por pestanejo

O QUE FALTAVA, E O QUE ESTE PORTAO FECHA: **nada disto era provado por nada.** O
comportamento estava certo e podia ser quebrado por qualquer edicao futura em
silencio -- e a nota do Superharness diz que um defeito corrigido sem controlo
volta. Aqui cada guarda tem um braco e um mutante que a derruba, e cada mutante
tem de derrubar O SEU braco.

    python _main\\external-resume-oracle.py            # rc=0 verde, rc=2 vermelho
    python _main\\external-resume-oracle.py --neg-arm  # rc=1 POR DESENHO

NAO lanca nada: importa a shell em processo (como `input-path-oracle.py`), monta
um `self` falso com os atributos que o metodo le, e conta as chamadas a
`start_worker`. Nao cria janela, nao instala hook, nao arranca worker.
"""
import argparse
import os
import sys
import time

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


def _stub(mod, **kw):
    class _Exit(object):
        def __init__(self, v):
            self.v = v

        def is_set(self):
            return self.v

    s = type('Stub', (), {})()
    s.exiting = _Exit(kw.get('exiting', False))
    s._external_parked = kw.get('parked', True)
    s._paused = kw.get('paused', False)
    s.visible = kw.get('visible', True)
    s._caption_window_shown = kw.get('caption', False)
    s.calls = []
    s.start_worker = lambda reason: (s.calls.append(reason), True)[1]
    if 'last' in kw:
        s._last_external_resume = kw['last']
    return s


def arms(mod, text):
    """[(rotulo, ok, detalhe)] -- cada braco julga UMA guarda."""
    fn = mod.SottoShell.on_external_captions_released
    seen = []
    mod.log = lambda m: seen.append(m)
    out = []

    s = _stub(mod, exiting=True)
    r = fn(s)
    out.append(('E1 shell a sair nao arranca worker', r is False and not s.calls,
                {'ret': r, 'calls': s.calls, 'log': seen[-1:]}))
    seen[:] = []

    s = _stub(mod, parked=False)
    r = fn(s)
    out.append(('E2 release sem park nao arranca', r is False and not s.calls,
                {'ret': r, 'calls': s.calls}))
    seen[:] = []

    s = _stub(mod, paused=True)
    r = fn(s)
    out.append(('E3 em pausa nao arranca', r is False and not s.calls,
                {'ret': r, 'calls': s.calls}))
    seen[:] = []

    s = _stub(mod, visible=False, caption=False)
    r = fn(s)
    out.append(('E4 escondido nao arranca', r is False and not s.calls,
                {'ret': r, 'calls': s.calls}))
    seen[:] = []

    s = _stub(mod, visible=False, caption=True)
    r = fn(s)
    out.append(('E5 a legenda visivel conta como visivel',
                r is True and s.calls == ['external-end'],
                {'ret': r, 'calls': s.calls}))
    seen[:] = []

    last = time.monotonic() - 1.0
    s = _stub(mod, last=last)
    r = fn(s)
    out.append(('E6 dentro dos 45 s: DEFERRED e o relogio nao anda',
                r is False and not s.calls
                and getattr(s, '_last_external_resume', None) == last
                and any('EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED' in m
                        for m in seen),
                {'ret': r, 'calls': s.calls, 'last': last,
                 'now': getattr(s, '_last_external_resume', None),
                 'log': seen[-1:]}))
    seen[:] = []

    s = _stub(mod)
    r = fn(s)
    out.append(('E7 caminho feliz arranca uma vez e marca o relogio',
                r is True and s.calls == ['external-end']
                and getattr(s, '_last_external_resume', 0.0) > 0.0,
                {'ret': r, 'calls': s.calls}))
    seen[:] = []

    s = _stub(mod, last=time.monotonic() - 100.0)
    r = fn(s)
    out.append(('E8 passados os 45 s volta a arrancar',
                r is True and s.calls == ['external-end'],
                {'ret': r, 'calls': s.calls}))
    return out


MUTANTS = [
    ('sem-guarda-exiting',
     'a shell a morrer deixa um worker ORFAO (E1)',
     """        if self.exiting.is_set():
            log('EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting')
            return False""",
     """        if False:
            log('EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting')
            return False""",
     'E1 shell a sair nao arranca worker'),
    ('sem-guarda-park',
     'um release sem park arranca o worker (E2)',
     """        if not self._external_parked:
            return False""",
     """        if False:
            return False""",
     'E2 release sem park nao arranca'),
    ('sem-guarda-pausa',
     'em pausa arranca o worker (E3)',
     """        if self._paused:
            return False""",
     """        if False:
            return False""",
     'E3 em pausa nao arranca'),
    ('sem-guarda-visivel',
     'escondido arranca o worker (E4)',
     """        if not (self.visible or getattr(self, '_caption_window_shown', False)):
            return False""",
     """        if False:
            return False""",
     'E4 escondido nao arranca'),
    ('legenda-nao-conta',
     'a legenda visivel deixa de contar como visivel (E5)',
     """        if not (self.visible or getattr(self, '_caption_window_shown', False)):
            return False""",
     """        if not self.visible:
            return False""",
     'E5 a legenda visivel conta como visivel'),
    ('sem-piso-45s',
     'o piso de 45 s desaparece: o pestanejo do player costa uma carga (E6)',
     """        if last and waited < EXTERNAL_RESUME_MIN_S:""",
     """        if False:""",
     'E6 dentro dos 45 s: DEFERRED e o relogio nao anda'),
    ('relogio-antes-do-piso',
     'o relogio anda mesmo quando o arranque e adiado (E6)',
     """        now = time.monotonic()
        last = getattr(self, '_last_external_resume', 0.0)
        waited = now - last""",
     """        now = time.monotonic()
        last = getattr(self, '_last_external_resume', 0.0)
        self._last_external_resume = now
        waited = now - last""",
     'E6 dentro dos 45 s: DEFERRED e o relogio nao anda'),
    ('relogio-nao-anda',
     'o caminho feliz nao marca o relogio, logo o piso nunca se aplica (E7)',
     """        self._last_external_resume = now""",
     """        pass""",
     'E7 caminho feliz arranca uma vez e marca o relogio'),
]


def _run(mod):
    return {label.split()[0]: (ok, got)
            for label, ok, got in arms(mod, _read(SHELL))}


def neg_arm():
    text = _read(SHELL)
    caught = 0
    for name, why, old, new, arm in MUTANTS:
        try:
            path = build_mutant(text, name, old, new)
            mmod = load_module(path, 'extresume_%s' % name.replace('-', '_'))
            got = _run(mmod)
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
                    help='os 8 mutantes tem de derrubar O SEU braco')
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
    print('braços: %d verdes, %d vermelhos' % (len(results) - bad, bad))
    print('EXTERNAL-RESUME VERDICT %s' % ('PASS' if not bad else 'FAIL'))
    return 0 if not bad else 2


if __name__ == '__main__':
    sys.exit(main())
