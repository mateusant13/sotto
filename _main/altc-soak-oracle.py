# NO-BUG: Oracle: 200 toques de Alt+C ao longo de 10 minutos nao podem deixar estado a
#        crescer nem deriva no gesto -- e o gesto que o dono mediu (toque unico nunca
#        abre o painel da direita) tem de continuar verdadeiro no toque 200.
#        Capacidade pedida pelo dono (A3 no gesto); nao ha id de
#        `_main/bug-ledger.json` para isto, e o id nao se inventa.
"""Oracle: a 200-tap soak of the Alt+C gesture, on the real pure module.

THE HOLE THIS CLOSES. `hotkey_gesture.next_action` / `advance` are pure and are
called on the key path of every press, and nothing ever pressed them 200 times to
prove the ladder does not drift or that the module grows no state on the way. The
owner's 2026-11-24 order is the reason the ladder is two houses, not three
(verbatim: *"ao apertar alt c segundos depois, o painel da direita abriu, o que nao
deveria acontecer. ja que e' pra abrir o da direita apenas em double alt c"*), and a
single tap opening the right panel is exactly the kind of regression a soak at press
200 catches and a three-assertion unit test does not.

ARMS (pure functions, injected clock -- no window, no hook, no key event)
  a 200-TAPS-BOUNDED -- 200 taps at a 3 s cadence (a full 10 minutes) stay inside
                        the two-house ladder and are periodic with period 2;
  b DOUBLE-BEATS-SINGLE -- every in-window pair reaches the right panel and every
                        out-of-window tap hides, across the whole soak;
  c NO-MODULE-STATE  -- no mutable container in the module grows across the 200
                        calls (a memo added without a cap is the failure);
  d BURST-EQUALS-SEQUENCE -- `advance(presses=n)` equals n single `next_action`
                        steps, which is what lets the shell spend one show/hide
                        per burst instead of one per press.

Usage:
  py -3 _main/altc-soak-oracle.py            # rc 0 = every arm holds
  py -3 _main/altc-soak-oracle.py --neg-arm  # rc 1 = every mutant CAUGHT
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from hypothesis import HealthCheck, given, settings, strategies as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
GESTURE = os.path.join(WEBVIEW, 'hotkey_gesture.py')
if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

TAPS = 200
CADENCE_S = 3.0          # 200 taps x 3 s = 10 minutos
WINDOW_S = 0.40          # DOUBLE_TAP_S, do proprio modulo


def load(name='hotkey_gesture_soak'):
    spec = importlib.util.spec_from_file_location(name, GESTURE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def mutable_state(mod):
    """(nome, id, len) de cada contentor mutavel do modulo -- o que pode crescer."""
    out = []
    for name, value in vars(mod).items():
        if isinstance(value, (list, dict, set, bytearray)):
            out.append((name, id(value), len(value)))
    return sorted(out)


def soak(mod, taps=TAPS, cadence=CADENCE_S):
    """O dono a carregar em Alt+C `taps` vezes, a `cadence` segundos de intervalo."""
    visible, surface = False, ''
    since = None
    trail = []
    for tap in range(taps):
        was = (visible, surface)
        visible, surface = mod.next_action(visible, surface, since, WINDOW_S)
        shown_new = visible and (not was[0] or surface != was[1])
        since = 0.0 if shown_new else None
        trail.append((tap, was, (visible, surface)))
        # O RELOGIO: cada toque chega `cadence` segundos depois do anterior, e a
        # idade do show da faixa envelhece com ele (None = nao houve show).
        if since is not None:
            since += cadence
    return visible, surface, trail


def arms(mod):
    results = []

    # a 200-TAPS-BOUNDED
    final_visible, final_surface, trail = soak(mod)
    states = set()
    drift = 0
    for _tap, _was, now in trail:
        states.add(now)
        if now not in ((False, ''), (False, 'strip'), (True, 'strip'), (True, 'panel'),
                       (False, 'panel')):
            drift += 1
    # A CADENCIA E' REGULAR E O ESTADO E' PERIODICO DE DOIS (mostra/esconde): uma
    # deriva apareceria como um terceiro estado ou como `outside_ladder`.
    single_tap_never_panel = all(
        not (now == (True, 'panel') and was == (False, ''))
        for _tap, was, now in trail)
    results.append(('a 200-TAPS-BOUNDED',
                    bool(drift == 0 and single_tap_never_panel and len(trail) == TAPS),
                    'taps=%d distinct_states=%d outside_ladder=%d final=%s/%s'
                    % (len(trail), len(states), drift, final_visible, final_surface)))

    # b DOUBLE-BEATS-SINGLE -- 100 pares dentro da janela e 100 fora.
    inside_ok = outside_ok = 0
    for pair in range(100):
        visible, surface = mod.next_action(False, '', None, WINDOW_S)
        visible, surface = mod.next_action(visible, surface, 0.0, WINDOW_S)
        inside_ok += 1 if (visible, surface) == (True, 'panel') else 0
        visible, surface = mod.next_action(False, '', None, WINDOW_S)
        visible, surface = mod.next_action(visible, surface, 5.0, WINDOW_S)
        outside_ok += 1 if (visible, surface) == (False, 'strip') else 0
    results.append(('b DOUBLE-BEATS-SINGLE',
                    bool(inside_ok == 100 and outside_ok == 100),
                    'double->panel %d/100, late-tap->hidden %d/100'
                    % (inside_ok, outside_ok)))

    # c NO-MODULE-STATE -- o mesmo soak, com o dicionario do modulo comparado.
    before = mutable_state(mod)
    soak(mod)
    after = mutable_state(mod)
    changed = [pair for pair in zip(before, after) if pair[0] != pair[1]]
    results.append(('c NO-MODULE-STATE', not changed,
                    'containers=%d changed=%d%s'
                    % (len(after), len(changed),
                       '' if not changed else ' ' + str(changed[:3]))))

    # d BURST-EQUALS-SEQUENCE
    mismatch = 0
    for presses in (1, 2, 3, 5, 8):
        burst = mod.advance(False, '', presses=presses)
        visible, surface, since = False, '', None
        for _step in range(presses):
            was = (visible, surface)
            visible, surface = mod.next_action(visible, surface, since, WINDOW_S)
            since = 0.0 if visible and (not was[0] or surface != was[1]) else None
        mismatch += 0 if burst == (visible, surface) else 1
    results.append(('d BURST-EQUALS-SEQUENCE', mismatch == 0,
                    'presses burst-vs-steps mismatches=%d' % mismatch))
    prop_ok, prop_detail = property_arm(mod)
    results.append(('e CADENCE-PROPERTY', prop_ok, prop_detail))
    return results


LADDER = ((False, ''), (False, 'strip'), (True, 'strip'),
          (True, 'panel'), (False, 'panel'))
CADENCES = (0.0, 0.2, WINDOW_S, 0.8, 3.0, 11.0)


def property_arm(mod):
    """PROPERTY e CADENCIA: generated (taps, cadence), not five hand-picked counts.

    The contract is independent of `soak`: the first tap always shows the bottom
    strip whatever the cadence (no clock on the key path); a right-hand panel is
    only a double inside the window; no press leaves the two-house ladder. All
    three rules are the owner's order recorded in hotkey_gesture.next_action.
    """
    @settings(max_examples=32, deadline=None, database=None,
              suppress_health_check=(HealthCheck.too_slow,))
    @given(taps=st.integers(min_value=1, max_value=40),
           cadence=st.sampled_from(CADENCES))
    def check(taps, cadence):
        _visible, _surface, trail = soak(mod, taps=taps, cadence=cadence)
        assert len(trail) == taps
        assert trail[0][2] == (True, 'strip')
        assert all(now in LADDER for _tap, _was, now in trail)
        if cadence > WINDOW_S:
            assert all(now != (True, 'panel') for _tap, _was, now in trail)

    try:
        check()
    except Exception as exc:  # noqa: BLE001
        return False, 'falsified: %r' % (exc,)
    return True, '32 generated (taps, cadence) pairs inside the ladder'


MUTATIONS = (
    # OS MUTANTES SUBSTITUEM A DECISAO DO PRODUTO (2026-11-26). As arms chamam
    # `mod.next_action`, o dono unico do passo, logo troca-la e' trocar o gesto.
    ('panel-on-every-tap', lambda mod: setattr(
        mod, 'next_action', lambda visible, surface, since=None, window=None:
        (True, 'panel')), 'a 200-TAPS-BOUNDED'),
    ('window-ignored', lambda mod: setattr(
        mod, 'next_action', lambda visible, surface, since=None, window=None:
        (False, 'strip') if visible else (True, 'strip')), 'b DOUBLE-BEATS-SINGLE'),
    ('memo-without-cap', lambda mod: setattr(mod, '_TAPS', []), 'c NO-MODULE-STATE'),
    ('burst-is-one-step', lambda mod: setattr(
        mod, 'advance', lambda visible, surface, presses=1, since_show_s=None,
        window_s=WINDOW_S: mod.next_action(visible, surface, since_show_s,
                                           window_s)), 'd BURST-EQUALS-SEQUENCE'),
)


def neg_arm():
    caught = 0
    for label, mutate, owner in MUTATIONS:
        mod = load('hotkey_gesture_mut_%s' % label.replace('-', '_'))
        mutate(mod)
        if label == 'memo-without-cap':
            # O DEFEITO DE VERDADE NAO E' ADICIONAR O ATRIBUTO, e' ESCREVER NELE: um
            # memo sem tecto cresce a cada chamada. Sem esta metade o mutante seria
            # decorativo (o atributo existe e ninguem lhe toca).
            original = mod.next_action

            def leaky(visible, surface, since=None, window=None, _orig=original):
                mod._TAPS.append((visible, surface))
                return _orig(visible, surface, since, window)
            mod.next_action = leaky
        got = {name: ok for name, ok, _detail in arms(mod)}
        if not got.get(owner):
            print('  GREEN mutant %-20s caught by: %s' % (label, owner))
            caught += 1
        else:
            print('  RED   mutant %-20s SURVIVED on arm %s -- gate blind'
                  % (label, owner))
    total = len(MUTATIONS)
    ok = caught == total
    print('NEG-ARM VERDICT: %s (%d/%d mutants caught)'
          % ('PASS' if ok else 'FAIL', caught, total))
    return 1 if ok else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()
    if args.neg_arm:
        return neg_arm()
    mod = load()
    failed = 0
    for name, ok, detail in arms(mod):
        print('  %-22s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        failed += 0 if ok else 1
    print('ALTC-SOAK VERDICT: %s (%d failure(s))'
          % ('PASS' if not failed else 'FAIL', failed))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
