"""O PLACEHOLDER "carregando modelo" NAO APAGA A LEGENDA -- oraculo.

O DEFEITO MEDIDO (2026-11-03, instancia viva pid 8168, `_main/webview-run.log`):

    10:45:53  BRIDGE_LOAD_MS ms=5390 pid=13888 worker_load_s=5.1     <- modelo PRONTO
    10:47:39  CAPTION_APPLIED count=1 text="S vake accounts I ask you..."
    ...
    10:50:30  CAPTION_OVERLAY_PUSH count=50 visible=true text="carregando modelo..."

Cinco minutos DEPOIS de o modelo estar carregado, e com 49 legendas aplicadas pelo
meio, a janela nativa voltou a pintar `carregando modelo...`. O caminho e' o
handler de `status` do `WorkerBridge`: o worker volta a publicar
`state=model-loading` (recarga, rotacao de dispositivo) e cada um desses chamava
`on_loading_text`, que a shell liga a `push_caption_to_window` -- o placeholder
pinta ATRAVES do mesmo canal da legenda, logo substitui-a no ecra.

O QUE ESTE ORACULO JULGA (`_consume` REAL, mensagens JSON reais, sem processo):

  1. `model-loading` ANTES de o filho carregar  -> o placeholder SAI (1 push);
  2. `model-loading` DEPOIS de `model-loaded`   -> o placeholder NAO sai;
  3. um filho NOVO (`spawn_reset`) volta a ter
     direito ao placeholder                      -> sai outra vez;
  4. uma legenda real nunca e' escrita como se
     fosse placeholder (o canal e' o mesmo, mas
     as chamadas sao distinguiveis);
  5. NEG-ARM: numa COPIA do ficheiro, o guarda
     `and not self.loaded` e' removido e o arm 2
     tem de cair.

USO:
    python _main/loading-placeholder-oracle.py
    python _main/loading-placeholder-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
GUARD = "if state == 'model-loading' and not self.loaded:"


def load_shell(path=SHELL, name='sotto_webview_placeholder_oracle'):
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_bridge(module, pushes):
    """A ponte REAL, sem processo: `_consume` e' o codigo de producao."""
    bridge = module.WorkerBridge(
        command=module.default_python(),
        log=lambda _m: None,
        on_loading_text=lambda text: pushes.append(text),
        worker_path=os.path.join(ROOT, 'worker', 'sotto_worker.py'),
    )
    return bridge


def feed(bridge, **message):
    bridge._consume(json.dumps(message))


def arms(module):
    out = []

    # 1. ANTES DE CARREGAR, o placeholder e' a informacao certa.
    pushes = []
    b = make_bridge(module, pushes)
    feed(b, type='status', state='model-loading')
    out.append(('placeholder-before-load', len(pushes) == 1,
                'pushes=%d (esperado 1)' % len(pushes)))

    # 2. DEPOIS DE CARREGAR, um `model-loading` atrasado NAO PODE apagar a legenda.
    pushes = []
    b = make_bridge(module, pushes)
    feed(b, type='status', state='model-loading')     # 1, legitimo
    feed(b, type='status', state='model-loaded')
    pushes_before = len(pushes)
    feed(b, type='status', state='model-loading')     # atrasado: tem de ser ignorado
    out.append(('late-loading-does-not-repaint', len(pushes) == pushes_before,
                'pushes=%d, depois do modelo carregado=%d (esperado igual e 1)'
                % (len(pushes), pushes_before)))

    # 3. UM FILHO NOVO TEM DIREITO AO PLACEHOLDER OUTRA VEZ (o reset por filho).
    #    O reset esta' no `_spawn`; aqui exercita-se o MESMO campo que ele limpa,
    #    porque largar um worker num oraculo seria largar uma app.
    pushes = []
    b = make_bridge(module, pushes)
    feed(b, type='status', state='model-loaded')
    b.loaded = False                                   # o que `_spawn` faz
    feed(b, type='status', state='model-loading')
    out.append(('new-child-can-show-placeholder', len(pushes) == 1,
                'pushes=%d (esperado 1)' % len(pushes)))

    # 4. O CANAL E' O MESMO, MAS A LEGENDA E' UMA LEGENDA: `model-loading` nunca
    #    escreve texto de legenda e uma legenda nunca escreve placeholder.
    pushes = []
    b = make_bridge(module, pushes)
    feed(b, type='caption', text='uma frase dita', start=1.0, end=2.0)
    out.append(('caption-is-not-a-placeholder', pushes == [],
                'pushes=%d (esperado 0)' % len(pushes)))
    return out


def neg_arm():
    """MUTACAO: sem o guarda, o arm 2 tem de cair."""
    text = io.open(SHELL, encoding='utf-8', errors='replace').read()
    if GUARD not in text:
        print('NEG-ARM: FAIL -- o guarda nao esta no ficheiro (ancora ausente)')
        return 1
    mutant = text.replace(GUARD, "if state == 'model-loading':", 1)
    tmpdir = tempfile.mkdtemp(prefix='sotto-neg-placeholder-')
    path = os.path.join(tmpdir, 'sotto_webview.py')
    io.open(path, 'w', encoding='utf-8', newline='').write(mutant)
    try:
        module = load_shell(path, name='sotto_webview_placeholder_mutant')
        pushes = []
        b = make_bridge(module, pushes)
        feed(b, type='status', state='model-loading')
        feed(b, type='status', state='model-loaded')
        before = len(pushes)
        feed(b, type='status', state='model-loading')
        caught = len(pushes) > before
    finally:
        try:
            os.remove(path)
            os.rmdir(tmpdir)
        except OSError:
            pass
    print('NEG-ARM %-22s %s  pushes=%d, antes do mutante=%d'
          % ('guard-removed', 'PASS' if caught else 'FAIL', len(pushes), before))
    # A convencao da bateria: um `red-as-expected` declara rc=1.
    return 1 if caught else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    module = load_shell()
    results = arms(module)
    bad = 0
    for name, ok, note in results:
        print('%-38s %s  %s' % (name, 'GREEN' if ok else 'RED', note))
        if not ok:
            bad += 1
    print('VERDICT: %s (%d/%d arms)' % ('PASS' if bad == 0 else 'FAIL',
                                        len(results) - bad, len(results)))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
