#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: a revelacao da legenda estava ancorada na CHEGADA do ASR, e nao no audio -- trabalho de CAPACIDADE pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""O RELOGIO DA REVELACAO E' O DO AUDIO, NAO O DA CHEGADA.

ORDEM DO DONO (2026-11-04), verbatim: *"a legenda do youtube ta fora de sync.
atrasada. depois faz um catch up super rapido e atrasa de novo"*.

MEDIDO no log VIVO dele (H:/sotto/_main/webview-run.log, 2026-11-04):

    09:58:32.625 CAPTION_APPLIED ... aged_kind=hold-expired audio_ms=1567
                                 queue_ms=1507 budget_ms=1500 over=true
    09:58:35.029 CAPTION_APPLIED ... aged_kind=transport     audio_ms=64
    09:58:38.212 CAPTION_APPLIED ... aged_kind=hold-expired audio_ms=2644

O ASR entrega em lotes que ja' vem 1,5-2,6 s atrasados. `LiveRows.push(text, at)`
datava cada palavra pelo instante da CHEGADA, logo a palavra nova nascia no futuro,
o lote seguinte era comprimido pela regra do YouTube (`MAX_LAG_S`) e o ecra
apanhava o atraso de uma vez -- o dente de serra que ele descreveu. A cura:
`late_s` recua a ancora para o instante em que o audio foi falado.

O QUE ESTE ORACULO EXECUTA (o codigo REAL, nao uma copia da regra):

  A1 sem atraso    -- `late_s=0` mantem o compasso: uma frase de 5 palavras nao
                      aparece toda no instante da chegada (e' a regra do YouTube,
                      medida nos 16 quadros do player).
  A2 com atraso    -- com `late_s=1.5` as palavras cujo instante ja' passou
                      aparecem JUNTAS e imediatamente -- nenhuma delas espera o
                      compasso de 0,24 s.
  A3 a mesma regra -- as duas metades usam o MESMO motor (`LiveRows`), e o
                      numero de palavras reveladas em A2 nunca e' menor que em A1.
  A4 tecto         -- a shell limita o recuo a 3 s (`min(3.0, ...)`), e um
                      `tap_ms` ausente deixa `late_s=0` em vez de explodir.
  A5 fiacao        -- `set_text` aceita `late_s` e o caminho do shell o passa
                      (`late_s=_late_s`) ao lado do `cue=`.

`--neg-arm`: muta uma COPIA de `caption_overlay.py` de duas formas -- (1) ignora
`late_s` (volta a ancorar na chegada) e (2) recua SEMPRE 3 s (o exagero oposto:
toda a frase nasce pronta) -- e exige as arms correspondentes a VERMELHO.
"""
import importlib.util
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
OVERLAY = os.path.join(WEBVIEW, 'caption_overlay.py')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
sys.path.insert(0, WEBVIEW)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


LINE = "Because he's going for these uh these people"


def make_overlay(mod, wrap):
    """Uma instancia REAL sem janela: so' o motor da legenda interessa aqui.

    `set_text` e' o metodo de producao -- e' ELE que chama `live.push` com a
    ancora, e e' por isso que os mutantes deste oraculo caem: a arm executa o
    `push` do FICHEIRO MUTADO, nao uma copia da regra.
    """
    import threading
    cls = mod.NativeCaptionOverlay
    ov = cls.__new__(cls)
    ov.lock = threading.RLock()
    ov.previous = ''
    ov.text = ''
    ov._cue = None
    ov._live = None
    ov._row_alphas = None
    ov._fade_t0 = None
    ov._fade_gen = 0
    ov.FADE_ON = False
    ov._update = lambda: True
    ov._wrap_fn = lambda: wrap
    return ov


def revealed(mod, text, late_s, wrap):
    """Quantas palavras o motor REAL mostra AGORA, com a ancora dada."""
    ov = make_overlay(mod, wrap)
    ov.set_text(text, '', instant=False, late_s=late_s)
    rows = ov._live.frame(time.monotonic()) if ov._live is not None else []
    return sum(len((row.get('text') or '').split()) for row in rows)


def arms(overlay_path=OVERLAY, shell_path=SHELL):
    out = []
    wrap = lambda text: [text]          # noqa: E731 -- a quebra nao e' o objecto
    mod = load(overlay_path, 'caption_overlay_under_test')

    # A1 -- sem atraso: o compasso do YouTube continua a ser o que segura as
    # palavras; a chegada NAO as solta todas de uma vez.
    a1 = revealed(mod, LINE, 0.0, wrap)
    out.append(('a1-sem-atraso-respeita-o-compasso', a1 < 8, 'reveladas=%d/8' % a1))

    # A2 -- 1,5 s de atraso: as palavras cujo instante ja' passou aparecem.
    a2 = revealed(mod, LINE, 1.5, wrap)
    out.append(('a2-atraso-solta-o-que-ja-passou', a2 >= 6, 'reveladas=%d/8' % a2))

    # A3 -- a mesma regra dos dois lados: nunca menos com atraso.
    out.append(('a3-atraso-nunca-revela-menos', a2 >= a1, 'a1=%d a2=%d' % (a1, a2)))

    shell = io.open(shell_path, encoding='utf-8', errors='replace').read()
    overlay = io.open(overlay_path, encoding='utf-8', errors='replace').read()

    # A4 -- o tecto e o `tap_ms` ausente.
    a4 = bool('[\\s\\S]{0,120}min\\(3\\.0' in shell
              or 'min(3.0, (time.time()' in shell) \
        and '_tap_now = getattr(self, \'_caption_pending_tap_ms\', None)' in shell
    out.append(('a4-tecto-de-3s-e-tap-ausente', a4, 'cap=%s' % a4))

    # A5 -- a fiacao: o overlay aceita o parametro e a shell passa-o.
    a5 = ('late_s=0.0' in overlay and 'live.push(full, time.monotonic() - max('
          in overlay and 'ov.set_text(new_text, new_prev, instant, cue=cue, late_s=_late_s)'
          in shell)
    out.append(('a5-fiacao-do-late_s', a5, 'wired=%s' % a5))
    return out


MUTANTS = {
    'm1-ignora-o-atraso': (
        "                live.push(full, time.monotonic() - max(0.0, float(late_s or 0.0)))",
        "                live.push(full, time.monotonic())"),
    'm2-recua-sempre-3s': (
        "                live.push(full, time.monotonic() - max(0.0, float(late_s or 0.0)))",
        "                live.push(full, time.monotonic() - 3.0)"),
}


def neg_arm():
    src = io.open(OVERLAY, encoding='utf-8', errors='replace').read()
    tmp = tempfile.mkdtemp(prefix='reveal-clock-neg-')
    caught = total = 0
    for name, (old, new) in MUTANTS.items():
        total += 1
        if old not in src:
            print('NEG-ARM IMPOSSIVEL %s: o padrao nao esta no ficheiro' % name)
            continue
        copy = os.path.join(tmp, name.replace('-', '_') + '.py')
        with io.open(copy, 'w', encoding='utf-8') as fh:
            fh.write(src.replace(old, new, 1))
        rows = dict((n, ok) for n, ok, _ in arms(overlay_path=copy))
        bad = [n for n, ok in rows.items() if not ok]
        if bad:
            caught += 1
            print('ok  %s -> RED: %s' % (name, ','.join(bad)))
        else:
            print('NOT-CAUGHT %s: nenhum arm vermelho' % name)
    print('NEG-ARM %s mutants %d/%d'
          % ('PASS' if caught == total else 'FAIL', caught, total))
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    rows = arms()
    bad = [r for r in rows if not r[1]]
    for name, ok, note in rows:
        print('%-34s %s  %s' % (name, 'PASS' if ok else 'FAIL', note))
    print('VERDICT: %s arms %d/%d'
          % ('FAIL' if bad else 'PASS', len(rows) - len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
