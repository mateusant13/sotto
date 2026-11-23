#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: ordem do dono de 2026-11-14 *"os paineis devem ficar ACIMA da legenda, no z index"* -- trabalho de CAPACIDADE sobre a composicao das janelas, sem id no `_main/bug-ledger.json`
"""O PAINEL FICA ACIMA DA LEGENDA? -- o portao do Z-order do dono (2026-11-14).

ORDEM DO DONO, verbatim: *"os paineis devem ficar ACIMA da legenda. no `z index`. a
legenda, agora mesmo, ta encima do painel, e eu nao consigo enxergar o painel bem"*.

O DEFEITO MEDIDO. As duas janelas sao TOPMOST. `caption_overlay.show(True)` corre a
CADA linha de legenda e faz `SetWindowPos(hwnd, HWND_TOPMOST)` (poe no topo da banda)
e logo `ShowWindow(SW_SHOWNOACTIVATE)` (re-mapeia ao topo da banda). Nada no codigo
punha a legenda abaixo do painel -- nao havia uma unica linha de Z-order relativo.

A SEMANTICA DO `SetWindowPos` FOI MEDIDA, nao lida (2026-11-14, janelas reais criadas
fora do ecra virtual e destruidas no fim; a prova esta' no cabecalho de
`app/webview/z_order.py` e no `insert_below` da shell):

    SetWindowPos(moved, insertAfter)  ->  insertAfter ACIMA de moved
    SetWindowPos(Y, HWND_TOP)         ->  Y acima de X          (controlo)

O QUE ESTE PORTAO EXECUTA (nenhuma janela visivel, nenhum dispositivo de audio):

  A1  `should_raise` e' FALSO sem as duas janelas visiveis, VERDADEIRO so' quando a
      legenda esta' por cima -- e o par de handles iguais nunca e' "acima".
  A2  `is_above` sobe a cadeia real e responde na direcao certa (corrente de 3).
  A3  `ZAuthority.ensure` com a legenda por cima: UMA chamada,
      `insert_below(caption, panel)`, e a linha `Z_ORDER_RAISED`.
  A4  ja' ordenado: ZERO escrita (o caso normal nao paga USER32).
  A5  legenda escondida: ZERO escrita.
  A6  painel escondido: ZERO escrita.
  A7  `insert_below` levanta: `Z_ORDER_RAISE_FAILED`, devolve False, o chamador vive.
  A8  `insert_below` recusa: `Z_ORDER_RAISE_REFUSED`, e o contador NAO sobe.
  A9  a caminhada respeita o tecto e uma cadeia em ciclo termina (sem falso positivo).
  A10 `caption_overlay.show` poe a legenda abaixo do painel DEPOIS de se erguer --
      medido na ORDEM das operacoes dentro da funcao real, nao na presenca do nome.
  A11 a shell passa o provedor (`z_below =`) na criacao do overlay.
  A12 a shell chama `_raise_above_caption` nos TRES caminhos de show.
  A13 a shell passa `extra=` ao `TopmostKeepalive` (o bit pode estar la' e a ordem
      nao), e o laco executa o extra mesmo quando nao ha nada a re-afirmar.

BRACO NEGATIVO. `--neg-arm` muta COPIA e exige cada mutante apanhado pelo SEU braco:
M1 `should_raise` sempre False (A3), M2 `is_above` sempre True (A3), M3 a insercao
antes do `ShowWindow` (A10), M4 o provedor apagado da shell (A11), M5 o `extra=`
apagado da shell (A13). O codigo testado e' a copia, nunca o original.
"""

import ast
import io
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ZMOD = os.path.join(REPO, 'app', 'webview', 'z_order.py')
OVERLAY = os.path.join(REPO, 'app', 'webview', 'caption_overlay.py')
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')


def read(path):
    return io.open(path, 'r', encoding='utf-8', newline='').read()


def load_module(path):
    mod = types.ModuleType('z_order_under_test')
    src = read(path)
    exec(compile(src, path, 'exec'), mod.__dict__)
    return mod


class FakeZ(object):
    """Um Z-order de brinquedo: `order` e' a lista do TOPO para o fundo."""

    def __init__(self, order, visible=None, write_ok=True, write_raises=None):
        self.order = list(order)
        self.visible = dict(visible or {})
        self.write_ok = write_ok
        self.write_raises = write_raises
        self.calls = []
        self.logs = []

    def visible_of(self, h):
        return bool(self.visible.get(int(h), True))

    def prev_of(self, h):
        h = int(h)
        if h not in self.order:
            return 0
        i = self.order.index(h)
        return self.order[i - 1] if i > 0 else 0

    def insert_below(self, moved, insert_after):
        self.calls.append((int(moved), int(insert_after)))
        if self.write_raises:
            raise self.write_raises
        if not self.write_ok:
            return False
        # a semantica MEDIDA: `insert_after` fica ACIMA de `moved`
        moved, ins = int(moved), int(insert_after)
        if moved in self.order:
            self.order.remove(moved)
        j = self.order.index(ins) if ins in self.order else len(self.order)
        self.order.insert(j + 1, moved)
        return True

    def log(self, line):
        self.logs.append(line)

    def authority(self, mod, panel=0x10, caption=0x20):
        return mod.ZAuthority(lambda: panel, lambda: caption, self.visible_of,
                              self.prev_of, self.insert_below, self.log)


def armp(fn):
    def run(mod):
        try:
            ok, detail = fn(mod)
        except Exception as exc:                       # noqa: BLE001
            return False, 'EXCEPTION %r' % (exc,)
        return bool(ok), detail
    return run


# ── A1 ───────────────────────────────────────────────────────────────────────
@armp
def arm_decision(mod):
    m = mod.should_raise
    cases = [
        ((True, True, True), False, 'ordenado nao pede nada'),
        ((True, True, False), True, 'legenda por cima pede'),
        ((False, True, False), False, 'painel escondido nao pede'),
        ((True, False, False), False, 'legenda escondida nao pede'),
        ((False, False, False), False, 'nenhuma das duas'),
    ]
    bad = [why for args, want, why in cases if bool(m(*args)) != want]
    ok = not bad
    return ok, ('casos=%d maus=%r' % (len(cases), bad))


# ── A2 ───────────────────────────────────────────────────────────────────────
@armp
def arm_walk(mod):
    z = FakeZ([0x30, 0x20, 0x10])          # 0x30 topo, 0x10 fundo
    up32 = mod.is_above(0x30, 0x10, z.prev_of)
    dn = mod.is_above(0x10, 0x30, z.prev_of)
    same = mod.is_above(0x20, 0x20, z.prev_of)
    zero = mod.is_above(0, 0x10, z.prev_of)
    ok = (up32 is True and dn is False and same is False and zero is False)
    return ok, ('up=%r down=%r same=%r zero=%r' % (up32, dn, same, zero))


# ── A3 ───────────────────────────────────────────────────────────────────────
@armp
def arm_raise_when_caption_above(mod):
    z = FakeZ([0x20, 0x10])                # legenda em cima, painel em baixo
    auth = z.authority(mod)
    out = auth.ensure('show-strip')
    ok = (out is True and z.calls == [(0x20, 0x10)]
          and z.order == [0x10, 0x20]
          and auth.raised == 1
          and any('Z_ORDER_RAISED why=show-strip' in s for s in z.logs))
    return ok, ('out=%r calls=%r order=%r logs=%r'
                % (out, z.calls, z.order, z.logs))


# ── A4 ───────────────────────────────────────────────────────────────────────
@armp
def arm_noop_when_ordered(mod):
    z = FakeZ([0x10, 0x20])                # painel ja' em cima
    auth = z.authority(mod)
    out = auth.ensure('keepalive')
    ok = (out is False and z.calls == [] and auth.raised == 0 and not z.logs)
    return ok, 'out=%r calls=%r logs=%r' % (out, z.calls, z.logs)


# ── A5 / A6 ──────────────────────────────────────────────────────────────────
@armp
def arm_caption_hidden(mod):
    z = FakeZ([0x20, 0x10], visible={0x20: False})
    auth = z.authority(mod)
    out = auth.ensure('show-strip')
    return (out is False and z.calls == []), 'out=%r calls=%r' % (out, z.calls)


@armp
def arm_panel_hidden(mod):
    z = FakeZ([0x20, 0x10], visible={0x10: False})
    auth = z.authority(mod)
    out = auth.ensure('show-strip')
    return (out is False and z.calls == []), 'out=%r calls=%r' % (out, z.calls)


# ── A7 ───────────────────────────────────────────────────────────────────────
@armp
def arm_write_raises(mod):
    z = FakeZ([0x20, 0x10], write_raises=OSError('USER32 recusou'))
    auth = z.authority(mod)
    out = auth.ensure('show-side')
    ok = (out is False and len(z.calls) == 1 and auth.raised == 0
          and any('Z_ORDER_RAISE_FAILED why=show-side' in s for s in z.logs))
    return ok, 'out=%r calls=%r logs=%r' % (out, z.calls, z.logs)


# ── A8 ───────────────────────────────────────────────────────────────────────
@armp
def arm_write_refused(mod):
    z = FakeZ([0x20, 0x10], write_ok=False)
    auth = z.authority(mod)
    out = auth.ensure('show-panel')
    ok = (out is False and len(z.calls) == 1 and auth.raised == 0
          and auth.calls == 1
          and any('Z_ORDER_RAISE_REFUSED why=show-panel' in s for s in z.logs))
    return ok, 'out=%r calls=%r raised=%d logs=%r' % (
        out, z.calls, auth.raised, z.logs)


# ── A9 ───────────────────────────────────────────────────────────────────────
@armp
def arm_chain_bounded(mod):
    # um ciclo: prev_of devolve sempre a mesma janela que nunca e' o alvo
    cycle = lambda h: 0x99
    out = mod.is_above(0x30, 0x10, cycle, 8)
    # alvo ALEM do tecto: nao pode ser encontrado
    chain = {}
    cur = 0x10
    for i in range(40):
        nxt = 0x100 + i
        chain[cur] = nxt
        cur = nxt
    deep = mod.is_above(0x100 + 39, 0x10, lambda h: chain.get(int(h), 0), 8)
    near = mod.is_above(0x100, 0x10, lambda h: chain.get(int(h), 0), 8)
    ok = (out is False and deep is False and near is True)
    return ok, 'cycle=%r deep=%r near=%r' % (out, deep, near)


# ── A10 ──────────────────────────────────────────────────────────────────────
def _fn_source(path, cls, name):
    src = read(path)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == name:
                    lines = src.splitlines()
                    return '\n'.join(lines[sub.lineno - 1:sub.end_lineno])
    return None


@armp
def arm_overlay_order(mod):
    body = _fn_source(OVERLAY, 'NativeCaptionOverlay', 'show')
    if body is None:
        return False, 'funcao show nao encontrada'
    i_show = body.find('SW_SHOWNOACTIVATE')
    # O `provider = self.z_below` e a insercao: os DOIS tem de vir DEPOIS do mapa
    # (`ShowWindow`), porque e' ele que re-mapeia a janela ao topo da banda. O
    # `ShowWindow(SW_HIDE)` do ramo de desligar tambem aparece no corpo, por isso
    # a ancora e' a linha que NOMEIA o `wt.HWND(below)` (a chamada que ordena).
    i_prev = body.find('provider = self.z_below')
    i_below = body.find('wt.HWND(below)')
    ok = (i_show >= 0 and i_prev > i_show and i_below > i_prev)
    return ok, ('show=%d provedor=%d insercao=%d (a insercao tem de vir DEPOIS do show)'
                % (i_show, i_prev, i_below))


# ── A11 / A12 / A13 ──────────────────────────────────────────────────────────
@armp
def arm_shell_provider(mod):
    src = read(SHELL)
    ok = src.count('self.caption_overlay.z_below = _z_below_provider') == 1
    return ok, 'occurrences=%d' % src.count('z_below')


@armp
def arm_shell_show_paths(mod):
    src = read(SHELL)
    counts = {lab: src.count("self._raise_above_caption('%s')" % lab)
              for lab in ('show-panel', 'show-strip', 'show-side')}
    ok = all(v == 1 for v in counts.values())
    return ok, 'counts=%r' % (counts,)


@armp
def arm_shell_keepalive_extra(mod):
    src = read(SHELL)
    tree = ast.parse(src)
    kw = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, 'attr', None) or getattr(fn, 'id', None)
            if name == 'TopmostKeepalive':
                kw = [k.arg for k in node.keywords]
                break
    return ('extra' in (kw or [])), 'keywords=%r' % (kw,)


@armp
def arm_keepalive_runs_extra(mod):
    """O extra roda TAMBEM quando o bit esta' la' -- o caso medido."""
    kp = types.ModuleType('topmost_keepalive_under_test')
    path = os.path.join(REPO, 'app', 'webview', 'topmost_keepalive.py')
    exec(compile(read(path), path, 'exec'), kp.__dict__)
    hits = []

    def extra():
        hits.append(1)
        raise RuntimeError('extra quebrado')   # e o laco tem de sobreviver

    logs = []
    ka = kp.TopmostKeepalive(
        0x10, lambda h: True, lambda h: kp.WS_EX_TOPMOST, lambda h: True,
        logs.append, extra=extra)
    first = ka.tick()          # bit presente -> nao re-afirma, MAS corre o extra
    second = ka.tick()
    ok = (first is False and second is False and len(hits) == 2
          and all('TOPMOST_EXTRA_FAILED' in s for s in logs)
          and ka.reasserted == 0)
    return ok, ('ticks_hits=%d reasserted=%d logs=%r'
                % (len(hits), ka.reasserted, logs[:3]))


# ── A15: A CHAMADA REAL, COM JANELAS REAIS (sem pixel no ecra) ────────────────
@armp
def arm_real_win32(mod):
    """O `insert_below` DA SHELL, executado contra o USER32, com duas janelas reais.

    Porque este braco existe: os outros catorze provam a DECISAO e a FIACAO, e o
    unico facto que nenhum deles toca e' a semantica do `SetWindowPos` -- que foi
    MEDIDA, nao lida, e cujo nome engana (o `insertAfter` fica ACIMA). Aqui as
    duas janelas sao criadas FORA do ecra virtual (o rect acaba antes da borda da
    uniao dos monitores), nunca ficam visiveis `on_screen`, e sao destruidas no
    `finally` -- a mesma tecnica que `caption-overlay-screen-oracle` ja' usa.

    A funcao testada e' o TEXTO da `insert_below` da shell, nao uma copia escrita
    aqui: uma copia passaria no dia em que a shell mudasse as bandeiras.
    """
    import ctypes
    import ctypes.wintypes as wt
    src = read(SHELL).replace('\r\n', '\n')
    tree = ast.parse(src)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'insert_below':
            fn = '\n'.join(src.splitlines()[node.lineno - 1:node.end_lineno])
            break
    if fn is None:
        return False, 'insert_below nao encontrada no fonte'

    u = ctypes.windll.user32
    u.CreateWindowExW.restype = wt.HWND
    u.CreateWindowExW.argtypes = [ctypes.c_uint, wt.LPCWSTR, wt.LPCWSTR,
                                  ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU,
                                  wt.HINSTANCE, wt.LPVOID]
    u.SetWindowPos.restype = wt.BOOL
    u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u.GetWindow.restype = wt.HWND
    u.GetWindow.argtypes = [wt.HWND, ctypes.c_uint]
    u.DestroyWindow.argtypes = [wt.HWND]
    u.GetSystemMetrics.argtypes = [ctypes.c_int]

    ns = {'user32': u, 'wt': wt, 'SWP_NOMOVE': 0x0002, 'SWP_NOSIZE': 0x0001,
          'SWP_NOACTIVATE': 0x0010}
    exec(compile(fn, '<insert_below>', 'exec'), ns)
    insert_below = ns['insert_below']

    WS_POPUP, WS_EX_TOPMOST, WS_EX_TOOLWINDOW = 0x80000000, 0x8, 0x80
    SW_SHOWNOACTIVATE, GW_HWNDPREV = 4, 3
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    off_x = u.GetSystemMetrics(SM_XVIRTUALSCREEN) - 400
    off_y = u.GetSystemMetrics(SM_YVIRTUALSCREEN) - 400
    made = []

    def mk(name):
        h = int(u.CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW, 'STATIC',
                                  name, WS_POPUP, off_x, off_y, 40, 20, None,
                                  None, None, None) or 0)
        made.append(h)
        return h

    def up(h):
        return int(u.GetWindow(wt.HWND(h), GW_HWNDPREV) or 0)

    def above(a, b):
        cur = b
        for _ in range(64):
            cur = up(cur)
            if not cur:
                return False
            if cur == a:
                return True
        return False

    try:
        caption = mk('zorder-arm-caption')
        panel = mk('zorder-arm-panel')
        if not caption or not panel:
            return False, 'janelas nao criadas (caption=%r panel=%r)' % (caption, panel)
        # a legenda ACIMA do painel, POSTA assim (o estado do defeito). A ordem
        # de criacao/mapa nao e' deterministica nesta caixa -- medido: mostrar a
        # segunda janela nao garante que ela fique por cima -- por isso o estado
        # inicial usa a MESMA primitiva: `insert_below(panel, caption)` deixa a
        # legenda por cima do painel (o `insertAfter` fica acima).
        insert_below(panel, caption)
        before = above(caption, panel)
        # e agora a chamada REAL da shell
        wrote = bool(insert_below(caption, panel))
        after = above(panel, caption)
        still = above(caption, panel)
        ok = (before is True and wrote is True and after is True
              and still is False)
        return ok, ('antes: legenda_acima=%r | escrita=%r | depois: painel_acima=%r '
                    'legenda_acima=%r' % (before, wrote, after, still))
    finally:
        for h in made:
            if h:
                try:
                    u.DestroyWindow(wt.HWND(h))
                except Exception:                     # noqa: BLE001
                    pass


# ── A16: A AUTORIDADE INTEIRA CONTRA O USER32 REAL ───────────────────────────
@armp
def arm_authority_real(mod):
    """`ZAuthority.ensure` de ponta a ponta, com o `GetWindow` e o `SetWindowPos`
    REAIS -- nenhum fake no caminho. Fecha o unico vao que A3 (decisao com fakes) e
    A15 (primitiva isolada) deixam entre si."""
    import ctypes
    import ctypes.wintypes as wt
    src = read(SHELL).replace('\r\n', '\n')
    tree = ast.parse(src)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'insert_below':
            fn = '\n'.join(src.splitlines()[node.lineno - 1:node.end_lineno])
            break
    if fn is None:
        return False, 'insert_below nao encontrada'

    u = ctypes.windll.user32
    u.CreateWindowExW.restype = wt.HWND
    u.CreateWindowExW.argtypes = [ctypes.c_uint, wt.LPCWSTR, wt.LPCWSTR,
                                  ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU,
                                  wt.HINSTANCE, wt.LPVOID]
    u.SetWindowPos.restype = wt.BOOL
    u.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u.GetWindow.restype = wt.HWND
    u.GetWindow.argtypes = [wt.HWND, ctypes.c_uint]
    u.IsWindowVisible.restype = wt.BOOL
    u.IsWindowVisible.argtypes = [wt.HWND]
    u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u.DestroyWindow.argtypes = [wt.HWND]
    u.GetSystemMetrics.argtypes = [ctypes.c_int]

    ns = {'user32': u, 'wt': wt, 'SWP_NOMOVE': 0x0002, 'SWP_NOSIZE': 0x0001,
          'SWP_NOACTIVATE': 0x0010}
    exec(compile(fn, '<insert_below>', 'exec'), ns)
    insert_below = ns['insert_below']

    WS_POPUP, WS_EX_TOPMOST, WS_EX_TOOLWINDOW = 0x80000000, 0x8, 0x80
    SW_SHOWNOACTIVATE, GW_HWNDPREV = 4, 3
    off_x = u.GetSystemMetrics(76) - 400
    off_y = u.GetSystemMetrics(77) - 400
    made, logs = [], []

    def mk(name):
        h = int(u.CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW, 'STATIC',
                                  name, WS_POPUP, off_x, off_y, 40, 20, None,
                                  None, None, None) or 0)
        made.append(h)
        u.ShowWindow(wt.HWND(h), SW_SHOWNOACTIVATE)
        return h

    panel, caption = 0, 0
    try:
        panel = mk('zorder-aut-panel')
        caption = mk('zorder-aut-caption')
        if not panel or not caption:
            return False, 'janelas nao criadas'
        insert_below(panel, caption)          # o defeito: legenda por cima
        auth = mod.ZAuthority(lambda: panel, lambda: caption,
                              lambda h: bool(u.IsWindowVisible(wt.HWND(h))),
                              lambda h: int(u.GetWindow(wt.HWND(h), GW_HWNDPREV) or 0),
                              insert_below, logs.append)
        state_before = auth.order_ok()[0]
        first = auth.ensure('show-strip')     # tem de agir
        state_after = auth.order_ok()[0]
        second = auth.ensure('keepalive')     # ja' ordenado: zero escrita
        ok = (state_before is False and first is True and state_after is True
              and second is False and auth.raised == 1 and auth.calls == 1
              and any('Z_ORDER_RAISED why=show-strip' in s for s in logs))
        return ok, ('antes_ok=%r agiu=%r depois_ok=%r 2a=%r raised=%d calls=%d'
                    % (state_before, first, state_after, second, auth.raised,
                       auth.calls))
    finally:
        for h in made:
            if h:
                try:
                    u.DestroyWindow(wt.HWND(h))
                except Exception:                     # noqa: BLE001
                    pass


ARMS = [
    ('A1-decisao', arm_decision),
    ('A2-caminhada', arm_walk),
    ('A3-poe-acima', arm_raise_when_caption_above),
    ('A4-ja-ordenado', arm_noop_when_ordered),
    ('A5-legenda-escondida', arm_caption_hidden),
    ('A6-painel-escondido', arm_panel_hidden),
    ('A7-escrita-levanta', arm_write_raises),
    ('A8-escrita-recusa', arm_write_refused),
    ('A9-caminhada-limitada', arm_chain_bounded),
    ('A10-overlay-ordem', arm_overlay_order),
    ('A11-shell-provedor', arm_shell_provider),
    ('A12-shell-shows', arm_shell_show_paths),
    ('A13-shell-extra', arm_shell_keepalive_extra),
    ('A14-extra-no-tique', arm_keepalive_runs_extra),
    ('A15-win32-real', arm_real_win32),
    ('A16-autoridade-real', arm_authority_real),
]


def run(zmod_path):
    mod = load_module(zmod_path)
    results = []
    for name, fn in ARMS:
        ok, detail = fn(mod)
        results.append((name, ok, detail))
        print('%-24s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
    bad = [n for n, ok, _ in results if not ok]
    print('VERDICT: %s (%d/%d arms)' % ('PASS' if not bad else 'FAIL',
                                        len(results) - len(bad), len(results)))
    return 0 if not bad else 1


# ── braco negativo ───────────────────────────────────────────────────────────
def mutate_copy(tmp, rel, changes):
    # CRLF/LF: o repo guarda estes ficheiros com CRLF e uma mutacao escrita com
    # '\n' nao casaria com nada -- foi medido aqui, como `(0)` de ocorrencias.
    # A copia normaliza para LF: o que os arms leem e' texto, e o `ast` do A13
    # aceita LF.
    src = read(os.path.join(REPO, rel)).replace('\r\n', '\n')
    for old, new in changes:
        if src.count(old) != 1:
            raise AssertionError('mutacao nao unica em %s: %r (%d)'
                                 % (rel, old[:40], src.count(old)))
        src = src.replace(old, new)
    dst = os.path.join(tmp, os.path.basename(rel))
    io.open(dst, 'w', encoding='utf-8', newline='').write(src)
    return dst


def neg_arm():
    global ZMOD, OVERLAY, SHELL
    caught = 0
    total = 0
    saved = (ZMOD, OVERLAY, SHELL)
    tmp = tempfile.mkdtemp(prefix='zorder-neg-')
    try:
        def attempt(label, rel, changes, want_arm):
            global ZMOD, OVERLAY, SHELL
            nonlocal caught, total
            total += 1
            try:
                path = mutate_copy(tmp, rel, changes)
            except AssertionError as exc:
                total += 1
                print('%-34s MUTATION-INVALID  %s' % (label, exc))
                ZMOD, OVERLAY, SHELL = saved
                return
            if rel.endswith('z_order.py'):
                ZMOD = path
            elif rel.endswith('caption_overlay.py'):
                OVERLAY = path
            else:
                SHELL = path
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = run(ZMOD)
            text = buf.getvalue()
            hit = rc != 0 and any(
                line.startswith('%-24s FAIL' % want_arm) for line in text.splitlines())
            caught += 1 if hit else 0
            print('%-34s %s  rc=%d  quer=%s'
                  % (label, 'CAUGHT' if hit else 'NOT-CAUGHT', rc, want_arm))
            ZMOD, OVERLAY, SHELL = saved

        attempt('M1 should_raise sempre False', 'app/webview/z_order.py',
                [("    if not panel_visible or not caption_visible:\n        return False\n    return not panel_above_caption",
                  "    return False")],
                'A3-poe-acima')
        attempt('M2 is_above sempre True', 'app/webview/z_order.py',
                [("    if not target or not below or target == below:\n        return False\n    cur = below\n    for _ in range(max(1, int(limit))):",
                  "    return True\n    cur = below\n    for _ in range(max(1, int(limit))):")],
                'A3-poe-acima')
        # M3: a insercao passa para ANTES do mapa -- a ordem mediu-se e e' o que
        # mantem a legenda abaixo do painel (o `ShowWindow` e' quem a re-ergue).
        attempt('M3 insercao antes do show', 'app/webview/caption_overlay.py',
                [("                _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)\n",
                  "                if below:\n"
                  "                    _user32.SetWindowPos(self.hwnd, wt.HWND(below),\n"
                  "                                         0, 0, 0, 0,\n"
                  "                                         SWP_NOMOVE | SWP_NOSIZE\n"
                  "                                         | SWP_NOACTIVATE)\n"
                  "                _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)\n")],
                'A10-overlay-ordem')
        attempt('M4 provedor apagado da shell', 'app/webview/sotto_webview.py',
                [("            self.caption_overlay.z_below = _z_below_provider\n",
                  "            pass\n")],
                'A11-shell-provedor')
        attempt('M5 extra apagado da shell', 'app/webview/sotto_webview.py',
                [("            interval=_topmost_keepalive.DEFAULT_INTERVAL_S,\n            extra=lambda: self._raise_above_caption('keepalive'))",
                  "            interval=_topmost_keepalive.DEFAULT_INTERVAL_S)")],
                'A13-shell-extra')
    finally:
        ZMOD, OVERLAY, SHELL = saved
        shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM: %s -- %d/%d' % ('PASS' if caught == total else 'FAIL',
                                    caught, total))
    return 1 if caught == total else 0


if __name__ == '__main__':
    if '--neg-arm' in sys.argv:
        sys.exit(neg_arm())
    sys.exit(run(ZMOD))
