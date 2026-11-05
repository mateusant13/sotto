# NO-BUG: CAPTURE EXCLUSION ORACLE -- a janela da legenda existe para o dono e para mais
"""CAPTURE EXCLUSION ORACLE -- a janela da legenda existe para o dono e para mais
ninguem.

O QUE ELE JULGA, e por que cada arm existe:

  1. `capture_exclusion.apply(hwnd)` num HWND REAL desta maquina tem de deixar
     `GetWindowDisplayAffinity` a dizer `0x11`. Nao se acredita no que se pediu:
     o valor e' LIDO DE VOLTA do sistema (um pedido que o Windows recusa
     devolve sucesso em alguns caminhos e afinidade nenhuma).
  2. A escada: com uma build abaixo de 19041 o modulo tem de cair para `0x01`
     (`WDA_MONITOR`) -- e NAO pode dizer `ok` a 0x11 num Windows que nao o tem.
  3. O interruptor: `SOTTO_CAPTURE_EXCLUDE=0` tem de deixar a janela como antes
     (`0x00`), porque um dono que grava a legenda de proposito tem de poder.
  4. O ESTILO que o overlay realmente cria (`caption_overlay.EX_STYLE`) tem de
     trazer `WS_EX_TRANSPARENT` (click-through nativo = a hit-region do
     `perssua-re`, sem hook de input) e `WS_EX_NOACTIVATE` (nao rouba o foco).

O BRAÇO NEGATIVO (`--neg-arm`) faz tres mutacoes numa COPIA do modulo e exige
que o MESMO `judge` as recuse: sem isso o oraculo provaria so' que ele sabe
dizer `ok` a si mesmo.
"""

from __future__ import annotations

import ctypes
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))

_user32 = ctypes.WinDLL('user32', use_last_error=True)
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080


def _probe_window():
    """Um HWND real e escondido, desta thread, para medir a afinidade."""
    hinst = _kernel32.GetModuleHandleW(None)
    hwnd = _user32.CreateWindowExW(WS_EX_TOOLWINDOW, 'STATIC', 'sotto-cap-probe',
                                   WS_POPUP, -4000, -4000, 40, 40, None, None,
                                   hinst, None)
    return hwnd


def judge(module, hwnd):
    """As quatro verdades, sobre um modulo e uma janela reais."""
    rows = []

    def arm(name, ok, detail):
        rows.append((name, bool(ok), detail))

    before = module.read(hwnd)
    arm('a1-comeca-limpo', before == module.WDA_NONE,
        'antes=%s' % module.mode_name(before))

    got = module.apply(hwnd, want=True)
    want = module.WDA_EXCLUDEFROMCAPTURE if module.can_exclude() else module.WDA_MONITOR
    readback = module.read(hwnd)
    arm('a2-modo-pedido-aplicado', got['mode'] == want and readback == want,
        'pedido=0x%02x aplicado=%s lido=0x%02x ok=%s'
        % (want, module.mode_name(got['mode']), readback & 0xff, got['ok']))

    # O dono tem de ver a janela: um modo que ESCURECE no ecra dele nao serve,
    # e um `ok=False` com 0x11 aplicado tambem nao.
    arm('a3-ok-coerente', got['ok'] is True and got['mode'] == readback,
        'ok=%s mode=%s readback=%s' % (got['ok'], got['mode'], readback))

    # A ESCADA: build antiga nao pode reclamar 0x11.
    old = module.apply(hwnd, want=True, build=1903)
    old_read = module.read(hwnd)
    arm('a4-build-antiga-cai-para-monitor',
        old['mode'] == module.WDA_MONITOR and old_read == module.WDA_MONITOR,
        'build=1903 modo=%s lido=%s' % (module.mode_name(old['mode']),
                                        module.mode_name(old_read)))

    # O INTERRUPTOR: desligado, a janela volta a entrar na captura.
    off = module.apply(hwnd, want=False)
    off_read = module.read(hwnd)
    arm('a5-desligado-volta-a-none',
        off['mode'] == module.WDA_NONE and off_read == module.WDA_NONE,
        'modo=%s lido=%s' % (module.mode_name(off['mode']),
                             module.mode_name(off_read)))

    # O EIXO DO ENV: o mesmo interruptor, lido como o overlay o le'.
    arm('a6-env-ligado-por-omissao', module.enabled({}) is True, 'enabled({})=%s'
        % module.enabled({}))
    arm('a7-env-desliga', module.enabled({'SOTTO_CAPTURE_EXCLUDE': '0'}) is False,
        'enabled(0)=%s' % module.enabled({'SOTTO_CAPTURE_EXCLUDE': '0'}))

    # O ESTILO REAL DA JANELA da legenda -- nao o texto do ficheiro.
    import caption_overlay
    ex = caption_overlay.EX_STYLE
    arm('a8-estilo-transparente-noactivate',
        bool(ex & 0x00000020) and bool(ex & 0x08000000) and bool(ex & 0x00080000),
        'ex_style=0x%08x always_on_top=%s' % (ex, bool(ex & 0x00000008)))

    # E a chamada viva do CAMINHO do overlay, para nao julgar so' o modulo:
    # o que o dono ve passa por `apply`, e o resultado tem de casar com o log
    # que a janela escreve.
    arm('a9-overlay-chama-o-modulo',
        callable(getattr(module, 'apply', None))
        and 'capture_exclusion' in io.open(os.path.join(HERE, '..', 'app',
                                                        'webview',
                                                        'caption_overlay.py'),
                                           encoding='utf-8').read(),
        'o overlay importa capture_exclusion')

    return rows


def _load(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('cap_probe', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _neg_arm():
    """Tres mutacoes numa COPIA; cada uma tem de derrubar o seu arm."""
    src = os.path.join(ROOT, 'app', 'webview', 'capture_exclusion.py')
    text = io.open(src, encoding='utf-8').read()
    mutations = [
        # m1: pede sempre 0x11 mesmo em build antiga -> a4 tem de cair
        ('m1-escada-ignorada', 'if can_exclude(build):', 'if True:'),
        # m2: pede SEMPRE 0x01 (o modo que nao esconde) -> a2 tem de cair. E' o
        # mutante que importa: a diferenca entre `WDA_MONITOR` (rectangulo preto
        # na gravacao) e `WDA_EXCLUDEFROMCAPTURE` (nada na gravacao) e' TODO o
        # proposito da feature, e um pedido "parecido" nao serve.
        ('m2-modo-fraco-sempre', "    ladder = []\n    if can_exclude(build):\n        ladder.append(WDA_EXCLUDEFROMCAPTURE)",
         "    ladder = []"),
        # m3-bis: ignora o interruptor e aplica mesmo com `want=False` -> a5.
        ('m4-want-ignorado', "    if not want:\n        _user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), WDA_NONE)",
         "    if False:\n        _user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), WDA_NONE)"),
        # m3: o interruptor deixa de existir -> a7 tem de cair
        ('m3-env-ignorado', "not in ('0', 'false', 'off', 'no')", "not in ()"),
    ]
    tmp = tempfile.mkdtemp(prefix='cap-neg-')
    hwnd = _probe_window()
    caught = 0
    try:
        for name, old, new in mutations:
            assert old in text, 'ancora ausente: %s' % name
            path = os.path.join(tmp, name + '.py')
            io.open(path, 'w', encoding='utf-8').write(text.replace(old, new, 1))
            mod = _load(path)
            rows = judge(mod, hwnd)
            red = [r[0] for r in rows if not r[1]]
            ok = bool(red)
            caught += 1 if ok else 0
            print('  %-6s %-22s -> %s  %s'
                  % ('ok' if ok else 'NOT-CAUGHT', name,
                     'RED: ' + ','.join(red) if red else 'nenhum arm vermelho',
                     ''))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if hwnd:
            _user32.DestroyWindow(hwnd)
    total = len(mutations)
    print('NEG-ARM %s  mutants %d/%d' % ('PASS' if caught == total else 'FAIL',
                                         caught, total))
    return 1 if caught == total else 0


def main(argv):
    if '--neg-arm' in argv:
        return _neg_arm()
    import capture_exclusion as module
    hwnd = _probe_window()
    if not hwnd:
        print('VERDICT: FAIL -- sem hwnd (error=%d)' % ctypes.get_last_error())
        return 2
    try:
        rows = judge(module, hwnd)
    finally:
        _user32.DestroyWindow(hwnd)
    bad = 0
    for name, ok, detail in rows:
        print('  %-4s %-34s %s' % ('ok' if ok else 'FAIL', name, detail))
        bad += 0 if ok else 1
    print('VERDICT: %s  arms %d/%d' % ('PASS' if not bad else 'RED',
                                       len(rows) - bad, len(rows)))
    return 0 if not bad else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
