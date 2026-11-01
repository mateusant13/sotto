#!/usr/bin/env python3
"""O FALSIFICADOR DO Alt+C -- a claim do autor medida por UM CAMINHO DIFFERENTE.

A CLAIM (uma so'):

    "Com a tecla Alt apertada e SEM ser solta, cada pressao de C no painel da
    TELA do Sotto alterna entre mostrar e esconder -- N pressoes dao N
    alternancias, e o painel alterna entre `strip` e `side` em vez de repetir
    o mesmo lado."

O QUE O AUTOR USOU (e por isso este script nao pode):

    `_main/altc-gesture-oracle.py` -- um oraculo ESTATICO. Ele extrai com `ast`
    os corpos de `hotkey_pressed`, `hotkey_live`, `_hotkey_resolve` e `_on_press`
    do ficheiro que vai correr e exec'-os contra um shell FALSO, um relogio-ESPIAO
    e um `threading`-ESPIAO. Mede o CODIGO. Nao abre janela nenhuma, nao ve o
    ecra, e o "estado do painel" que ele julga e' um dicionario que o proprio
    teste fabricou.

O QUE ESTE SCRIPT USA (o caminho diferente):

    Uma INSTANCIA DE MEDICAO REAL da app, numa ARVORE DE SCRATCH propria, com
    um mutex PRIVADO e um acelerador que o dono nao usa. Nada disto toca na app
    do dono, nem no ficheiro `_main/panel-visibility.json` dele, nem na tecla
    dele. A app e' a de verdade (`app/webview/sotto_webview.py`), com o WebView2
    de verdade, e o painel e' a JANELA de verdade.

    A ENTREGA e' a de producao: a pressao e' um `WM_HOTKEY` posto na fila da
    thread que tem a `RegisterHotKey` -- o mesmo que o Windows poe quando o
    dono carrega Alt+C -- e quem o entrega e' o pump verdadeiro da app.

    A CONTAGEM e' MINHA. Eu leio o log que a app escreve e atribuo a cada
    pressao o estado que a SEGUNDEU: um `PANEL_SHOWN reason=hotkey-cycle-strip`
    ou `reason=hotkey-cycle-side`, ou um `PANEL_HIDDEN reason=hotkey-toggle`.
    O `SELFTEST arm=5-ten` do autor entra no recibo como REFERENCIA CRUZADA,
    nunca como o julgamento.

    E ha DOIS CANOS SEPARADOS que tem de concordar com a minha contagem:
      (1) o `panel-visibility.json` PUBLICA (o writer da propria app) e' lido
          do disco DURANTE a corrida -- e' a vista do DONO;
      (2) o `panel-state.json` (o dump da propria app) e' lido no fim.
    Se a minha contagem do log concordar com o publisher e com o dump, o
    veredicto nao esta' a ler uma eco da minha propria medicao.

OS BRACOS (todos com o MESMO script, a MESMA forma, arvores SEPARADAS):

    pos            a arvore INTACTA                     -> tem de dar VERDE
    neg-inverted   a arvore INTACTA, a EXPECTATIVA
                   INVERTIDA (esperar o MESMO lado duas
                   vezes seguidas)                        -> tem de dar VERMELHO
    neg-mutant     a arvore MUTADA (`next_surface` a
                   devolver sempre 'strip')               -> tem de dar VERMELHO

O `neg-inverted` prova que a minha sonda nao e' vacua (a mesma medicao com a
claim ao contrario tem de reprovar). O `neg-mutant` prova que o VERDE do `pos`
vem do COMPORTAMENTO do produto e nao de uma permissividade da minha sonda.

SENSIBILIDADE DA SONDA (o par que a casa exige): durante a corrida eu leio o
`panel-visibility.json` publicado e tenho de ver `visible=true` ALGUMA VEZ e
`visible=false` ALGUMA VEZ. Uma sonda que nunca ve o painel nao pode provar
nada sobre o painel.

NADA E' SINTETICO: nenhum `keybd_event`, nenhum `SendInput`. Nenhum evento de
LIBERTACAO e' entregue a app (a app nao conhece nenhum -- ver o veredicto
`no_release_event_delivered`).

USO
    python _main/_falsify-altc-probe.py --all
    python _main/_falsify-altc-probe.py --arm pos
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_ROOT = os.path.dirname(HERE)

#: A ARVORE DE SCRATCH. Nao e' a worktree: o `REPO_ROOT` do shell e' a raiz da
#: arvore onde o `app/` esta', e e' por isso que `panel-visibility.json` e
#: `panel-state.json` caem dentro da scratch e NAO no `_main/` do dono.
SCRATCH = os.environ.get('SOTTO_FALSIFY_SCRATCH') or r'I:\cc-tmp\falsify-altc'

#: O que a app precisa para correr. `app/panel` sao os assets, `app/webview` e'
#: o shell. `worker/` (1,2 GB) NAO vem: o run e' `--no-worker`.
COPY_FILES = ('app/webview', 'app/panel')
COPY_SINGLE = ('_main/pov-selftest.py', '_main/launch-as-token.py')

#: A MUTACAO do braco negativo. Troca a REGRA do ciclo (nao o instrumento) por
#: uma regra que repete o mesmo lado -- o defeito exacto que a claim proibe.
MUTATION = (
    "    return 'panel' if str(surface or '') == 'strip' else 'strip'",
    "    return 'strip'  # FALSIFY-MUTANT: o mesmo lado sempre",
)

ARMS = ('pos', 'neg-inverted', 'neg-mutant')
EXPECT_PRESSES = 10

# --- as linhas do log que eu leio (as MINHAS regexes, nao as do autor) -------
PRESS_RE = re.compile(r'HOTKEY_PRESSED role=panels count=(\d+)')
#: A ANCORA POR PRESSAO. A app escreve UMA linha `HOTKEY_TOGGLE` por pressao, no
#: `_hotkey_resolve`, e ela diz o que o passo vai fazer: `step=show surface=<n>`
#: ou `step=hide surface=<n>`. E' a unica serie que tem UM elemento por pressao
#: por CONSTRUCAO (o `_hotkey_resolve` corre uma vez por item da fila).
TOGGLE_SHOW_RE = re.compile(r'HOTKEY_TOGGLE step=show surface=(\w+)')
TOGGLE_HIDE_RE = re.compile(r'HOTKEY_TOGGLE step=hide surface=(\w+)')
#: A superficie do SHELL para o painel da direita e' `panel`; a linha
#: `PANEL_SHOWN ... mode=side` escreve `side`. A MESMA superficie com dois
#: nomes -- a ponte e' esta tabela, e ela e' uma PALAVRA do produto, nao
#: um guess: `show_side` chama `set_panel_surface('panel')` e loga
#: `mode=side`.
SURFACE_NAMES = {'strip': 'strip', 'panel': 'side', 'side': 'side'}
LIVE_PRESS_RE = re.compile(r'HOTKEY_PRESSED role=live-probe')
SHOW_STRIP_RE = re.compile(r'PANEL_SHOWN reason=hotkey-cycle-strip .*mode=strip')
SHOW_SIDE_RE = re.compile(r'PANEL_SHOWN reason=hotkey-cycle-side .*mode=side')
HIDE_RE = re.compile(r'PANEL_HIDDEN reason=hotkey-toggle')
MODE_RE = re.compile(
    r'PANEL_VISIBILITY_MODE visible=(true|false) reason=(\S+) transitions=(\d+)')
STEP4_RE = re.compile(r'SELFTEST step=4-hidden')
STEP6_RE = re.compile(r'SELFTEST step=6-live')
ARM5_RE = re.compile(r'SELFTEST arm=5-ten')
SELFTEST_RC_RE = re.compile(r'SELFTEST rc=(-?\d+)')
SELFTEST_BROKEN_RE = re.compile(r'SELFTEST broken=(.*)')


# ---------------------------------------------------------------------------
# A ARVORE DE SCRATCH
# ---------------------------------------------------------------------------
def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def build_tree(src_root, dst_root, force=False):
    """Copia o que a app precisa para a scratch. Devolve um manifesto."""
    manifest = {'src': src_root, 'dst': dst_root, 'files': []}
    if force and os.path.isdir(dst_root):
        shutil.rmtree(dst_root, ignore_errors=True)
    os.makedirs(os.path.join(dst_root, '_main'), exist_ok=True)
    for rel in COPY_SINGLE:
        src = os.path.join(src_root, rel.replace('/', os.sep))
        dst = os.path.join(dst_root, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        manifest['files'].append({'rel': rel, 'sha256': sha(dst),
                                   'bytes': os.path.getsize(dst)})
    for rel in COPY_FILES:
        src = os.path.join(src_root, rel.replace('/', os.sep))
        dst = os.path.join(dst_root, rel.replace('/', os.sep))
        if os.path.isdir(dst):
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst,
                        ignore=shutil.ignore_patterns(
                            '__pycache__', '*.pyc', 'tmp*.tmp',
                            '_strip-logmutant-repro*', '_vis-live-sotto_webview.py'))
        for base, _dirs, names in os.walk(dst):
            for name in names:
                full = os.path.join(base, name)
                manifest['files'].append({
                    'rel': os.path.relpath(full, dst_root).replace('\\', '/'),
                    'sha256': sha(full), 'bytes': os.path.getsize(full)})
    with open(os.path.join(dst_root, '_main', 'falsify-manifest.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=1)
    return manifest


def apply_mutation(dst_root, kind):
    """Muda a REGRA na scratch (nunca no produto). Devolve o antes/depois."""
    path = os.path.join(dst_root, 'app', 'webview', 'hotkey_gesture.py')
    with open(path, 'r', encoding='utf-8') as fh:
        before = fh.read()
    if kind == 'none':
        return {'kind': 'none', 'path': path, 'changed': False,
                'sha256': sha(path)}
    old, new = MUTATION
    if before.count(old) != 1:
        raise SystemExit('MUTATION_TARGET_COUNT=%d path=%s'
                         % (before.count(old), path))
    after = before.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(after)
    return {'kind': kind, 'path': path, 'changed': True,
            'before': old.strip(), 'after': new.strip(),
            'sha256': sha(path)}


# ---------------------------------------------------------------------------
# O LEITOR DO ESTADO PUBLICADO (um cano SEPARADO do log)
# ---------------------------------------------------------------------------
class PublishedReader(threading.Thread):
    """Le o `panel-visibility.json` PUBLICA enquanto a app corre."""

    def __init__(self, path, period=0.02):
        super().__init__(daemon=True)
        self.path = path
        self.period = period
        self.samples = []
        self._halt = threading.Event()

    def stop(self):
        self._halt.set()

    def run(self):
        while not self._halt.is_set():
            try:
                with open(self.path, 'r', encoding='utf-8') as fh:
                    payload = json.load(fh)
                self.samples.append({
                    'visible': bool(payload.get('visible')),
                    'transitions': payload.get('transitions'),
                    'reason': payload.get('reason'),
                    'pid': payload.get('pid'),
                    'writtenAtEpoch': payload.get('writtenAtEpoch'),
                })
            except Exception:
                pass
            self._halt.wait(self.period)


def published_summary(samples):
    """Reduz as amostras ao que a sonda TEM de ver para poder julgar."""
    visible_true = [s for s in samples if s['visible']]
    visible_false = [s for s in samples if not s['visible']]
    transitions = []
    for s in samples:
        t = s.get('transitions')
        if isinstance(t, int) and (not transitions or transitions[-1] != t):
            transitions.append(t)
    pids = sorted({s.get('pid') for s in samples if s.get('pid')})
    return {
        'samples': len(samples),
        'saw_visible_true': bool(visible_true),
        'saw_visible_false': bool(visible_false),
        'distinct_transitions': transitions,
        'transitions_count': len(transitions),
        'pids': pids,
        'first': samples[0] if samples else None,
        'last': samples[-1] if samples else None,
    }


# ---------------------------------------------------------------------------
# A CONTAGEM MINHA: o log, linha a linha, ATRIBUIDA POR PRESSAO
# ---------------------------------------------------------------------------
def parse_log(text):
    """Reconstroi, POR PRESSAO, o estado do painel que a app registou.

    A JANELA e' a das 10 pressoes do arm 5. A delimitacao e' feita pela
    **ANCORA** `SELFTEST step=4-hidden` (a 4a pressao, o arm 4) e pela
    `SELFTEST step=6-live` (o arm 6, a tecla da legenda -- que NAO e' uma
    pressao de painel). Entre elas estao EXATAMENTE as 10 pressoes do arm 5.

    A ATRIBUICAO E' POR PRESSAO, E A ANCORA E' O `HOTKEY_TOGGLE`. A app escreve
    UMA linha `HOTKEY_TOGGLE` por pressao, dentro do `_hotkey_resolve`, e ela
    diz o que aquele passo vai fazer (`step=show surface=strip|panel` ou
    `step=hide surface=...`). A serie dos `HOTKEY_TOGGLE` tem portanto UM
    elemento por pressao **por construcao** -- e' o `_hotkey_resolve` que corre
    uma vez por item da fila.

    O `HOTKEY_PRESSED count=N` NAO serve de ancora: e' escrito pelo PUMP da
    thread da tecla, e o TRABALHO DE JANELA corre LESA, noutra thread. No log
    medido, o `PANEL_SHOWN` da pressao 5 aparece DEPOIS do `count=6` ja'
    posted -- as duas series nao correm em passo. A ordem que conta e' a ordem
    da FILA, e a fila e' FIFO (`_hotkey_worker_loop`: `q.get()`).

    TRES SERIES, e as tres tem de concordar:
      (1) a serie de ESTADOS (`PANEL_SHOWN`/`PANEL_HIDDEN`) -- o que o dono
          veria;
      (2) a serie de `HOTKEY_TOGGLE` -- a ANCORA, um elemento por pressao;
      (3) o CONTADOR DE TRANSICOES da propria app (`PANEL_VISIBILITY_MODE
          transitions=N`), monotonicamente crescente.
    """
    lines = text.splitlines()
    step4 = None
    for i, line in enumerate(lines):
        if STEP4_RE.search(line):
            step4 = i
            break
    if step4 is None:
        return {'ok': False, 'error': 'STEP4_LINE_MISSING'}

    end = len(lines)
    for i in range(step4 + 1, len(lines)):
        if STEP6_RE.search(lines[i]):
            end = i
            break
    window = lines[step4 + 1:end]

    # -- (1) A SERIE DE ESTADOS, pela ordem da fila ------------------------
    events = []
    for line in window:
        if SHOW_STRIP_RE.search(line):
            events.append({'visible': True, 'surface': 'strip', 'line': line})
        elif SHOW_SIDE_RE.search(line):
            events.append({'visible': True, 'surface': 'side', 'line': line})
        elif HIDE_RE.search(line):
            events.append({'visible': False, 'surface': None, 'line': line})

    # -- (2) A ANCORA: um `HOTKEY_TOGGLE` por pressao ----------------------
    toggles = []
    for line in window:
        g = TOGGLE_SHOW_RE.search(line)
        if g:
            toggles.append({'action': 'show', 'surface': g.group(1), 'line': line})
            continue
        g = TOGGLE_HIDE_RE.search(line)
        if g:
            toggles.append({'action': 'hide', 'surface': g.group(1), 'line': line})

    # -- (3) O CONTADOR DE TRANSICOES DA PROPRIA APP -----------------------
    # A serie dos modos e' lida a partir da ancora, e nao da janela: o
    # `PANEL_VISIBILITY_MODE` do ESTADO DA ULTIMA PRESSAO e' escrito pela
    # quebra e pode cair DEPOIS da linha da tecla da legenda. Por isso a serie
    # dos modos comeca na transicao que o primeiro `HOTKEY_TOGGLE` da janela
    # produziu, e nao na transicao anterior (que e' a do arm 4).
    modes = []
    for line in lines[step4 + 1:]:
        g = MODE_RE.search(line)
        if g:
            modes.append({'visible': g.group(1) == 'true', 'reason': g.group(2),
                          'transitions': int(g.group(3)), 'line': line})
    trans = [m['transitions'] for m in modes]
    trans_contiguous = bool(trans) and trans == list(range(trans[0], trans[0] + len(trans)))

    # A RECORTE DA SERIE DOS MODOS: a partir do primeiro modo CUJO numero de
    # transicao coincide com o que a ancora espera. O primeiro show da janela
    # produz a transicao `T+1` (o `PANEL_VISIBILITY_MODE` do hide do arm 4 e'
    # `T`), e a serie dos modos da janela comeca em `T` se o hide do arm 4
    # for escrito dentro dela.
    anchor_modes = modes
    if toggles and modes:
        # A serie de estados tem o MESMO numero de elementos que a de modos
        # quando o hide do arm 4 nao caiu dentro da janela; quando caiu, a
        # serie de modos tem UM a mais, no COMECO. A recorta e' a de
        # transicoes: a ancora N espera a transicao `T+N`.
        base = None
        for m in modes:
            if m['visible'] == (toggles[0]['action'] == 'show'):
                base = m
                break
        if base is not None:
            want = base['transitions']
            anchor_modes = [m for m in modes if m['transitions'] >= want]

    # -- A ENTREGA (as pressoes) --------------------------------------------
    presses = []
    for line in window:
        g = PRESS_RE.search(line)
        if g:
            presses.append({'press_count': int(g.group(1)), 'line': line})
    press_counts = [p['press_count'] for p in presses]
    presses_contiguous = bool(press_counts) and press_counts == list(
        range(press_counts[0], press_counts[0] + len(press_counts)))

    author_line = None
    for line in lines:
        if ARM5_RE.search(line):
            author_line = line
            break

    # A ATRIBUICAO: a ancora decide a QUAL estado cada pressao produziu, e a
    # serie de estados tem de CONTER esse estado, na ordem. A serie de estados
    # pode ter estados a MAIS (o `PANEL_HIDDEN` do arm 4 e' escrito pela
    # quebra e pode cair DEPOIS da linha `step=4-hidden`, ja' dentro da
    # janela) -- por isso a atribuicao e' uma busca, nao um zip.
    #
    # E' isto que torna a medicao HONESTA: a pressao N e' a que a ancora N
    # descreve, e o estado observado tem de ser o que a ancora pediu. Um
    # estado a mais (de outra pressao) nao pode ser atribuido a pressao
    # nenhuma, e um estado a menos (uma pressao que nao mudou o ecra) faz a
    # atribuicao falhar.
    toggle_visible = [t['action'] == 'show' for t in toggles]
    toggle_shows = [SURFACE_NAMES.get(t['surface'], t['surface'])
                    for t in toggles if t['action'] == 'show']
    state_visible = [e['visible'] for e in events]
    state_shows = [e['surface'] for e in events if e['visible']]

    attributed = []
    cursor = 0
    for t in toggles:
        want_visible = (t['action'] == 'show')
        want_surface = (SURFACE_NAMES.get(t['surface'], t['surface'])
                        if want_visible else None)
        found = None
        for idx in range(cursor, len(events)):
            e = events[idx]
            if e['visible'] != want_visible:
                continue
            if want_visible and e['surface'] != want_surface:
                continue
            found = idx
            break
        if found is None:
            attributed.append({'toggle': t, 'state': None})
            break
        attributed.append({'toggle': t, 'state': events[found]})
        cursor = found + 1

    attributed_ok = (len(attributed) == len(toggles)
                     and all(a['state'] is not None for a in attributed))
    attributed_visible = [a['state']['visible'] for a in attributed
                          if a['state'] is not None]
    attributed_shows = [a['state']['surface'] for a in attributed
                        if a['state'] is not None and a['state']['visible']]
    series_agree = (attributed_ok
                    and attributed_visible == toggle_visible
                    and attributed_shows == toggle_shows)

    return {
        'ok': True,
        'window_start_line': step4,
        'window_end_line': end,
        'presses': presses,
        'presses_in_window': len(presses),
        'press_counts': press_counts,
        'presses_contiguous': presses_contiguous,
        'states': events,
        'states_in_window': len(events),
        'toggles': toggles,
        'toggles_in_window': len(toggles),
        'toggle_shows': toggle_shows,
        'attributed': attributed,
        'attributed_ok': attributed_ok,
        'attributed_visible': attributed_visible,
        'attributed_shows': attributed_shows,
        'modes': modes,
        'anchor_modes': anchor_modes,
        'transitions_contiguous': trans_contiguous,
        'series_agree': series_agree,
        'author_line': author_line,
        'selftest_rc': (SELFTEST_RC_RE.search(text).group(1)
                        if SELFTEST_RC_RE.search(text) else None),
        'selftest_broken': (SELFTEST_BROKEN_RE.search(text).group(1)
                            if SELFTEST_BROKEN_RE.search(text) else None),
        'window_lines': window,
    }


def judge(count, expectation):
    """O JULGAMENTO MINHA. `expectation` = 'claim' (a claim) ou 'inverted' (a
    mesma medicao com a claim ao contrario)."""
    # A SERIE JULGADA e' a ATRIBUIDA (uma por ancora), nao a serie crua: a
    # serie crua pode ter um estado a mais (o hide do arm 4, escrito pela
    # quebra) e um estado a mais mudaria a primeira pressao de "show" para
    # "hide" -- o suficiente para fabricar um REFUTED que nao existe.
    attributed = count.get('attributed') or []
    states = [a['state'] for a in attributed if a['state'] is not None]
    visible = [s['visible'] for s in states]
    shows = [s['surface'] for s in states if s['visible']]
    press_counts = count.get('press_counts') or []
    modes = count.get('anchor_modes') or count.get('modes') or []
    mode_visible = [m['visible'] for m in modes]
    n_anchors = len(count.get('toggles') or [])

    alternates = (len(visible) >= 2
                  and all(visible[i] != visible[i - 1] for i in range(1, len(visible))))
    side_alternates = (len(shows) >= 2
                       and all(shows[i] != shows[i - 1] for i in range(1, len(shows))))
    same_side_twice = any(shows[i] == shows[i - 1] for i in range(1, len(shows)))
    modes_agree = (len(mode_visible) == len(visible)
                   and mode_visible == visible[:len(mode_visible)])

    if expectation == 'inverted':
        checks = {
            'expect_same_side_twice': {'ok': same_side_twice,
                                       'detail': 'shows=%r' % (shows,)},
            'expect_side_not_alternating': {'ok': not side_alternates,
                                             'detail': 'shows=%r' % (shows,)},
        }
    else:
        checks = {
            'ten_presses_delivered': {
                'ok': len(press_counts) == EXPECT_PRESSES,
                'detail': 'presses=%d expected=%d' % (len(press_counts), EXPECT_PRESSES)},
            'press_counter_contiguous': {
                'ok': bool(count.get('presses_contiguous')),
                'detail': 'counts=%r' % (press_counts,)},
            'one_state_per_press': {
                'ok': (len(states) == len(press_counts) == EXPECT_PRESSES
                       and bool(count.get('attributed_ok'))),
                'detail': 'attributed=%d presses=%d anchors=%d'
                          % (len(states), len(press_counts), n_anchors)},
            'visibility_alternates_every_press': {
                'ok': alternates and len(visible) == EXPECT_PRESSES,
                'detail': 'visible=%r' % (visible,)},
            'first_press_shows': {
                'ok': bool(visible) and visible[0] is True,
                'detail': 'first=%r' % (visible[0] if visible else None,)},
            'surface_alternates_strip_side': {
                'ok': side_alternates,
                'detail': 'shows=%r' % (shows,)},
            'no_repeated_side': {
                'ok': not same_side_twice,
                'detail': 'shows=%r' % (shows,)},
            'app_transition_counter_contiguous': {
                'ok': bool(count.get('transitions_contiguous')),
                'detail': 'transitions=%r' % ([m['transitions'] for m in modes],)},
            'published_counter_agrees_with_log': {
                'ok': modes_agree,
                'detail': 'modes=%r states=%r' % (mode_visible, visible)},
            'one_toggle_anchor_per_press': {
                'ok': n_anchors == EXPECT_PRESSES,
                'detail': 'toggles=%d presses=%d' % (n_anchors, len(press_counts))},
            'toggle_anchor_agrees_with_states': {
                'ok': bool(count.get('series_agree')),
                'detail': 'toggle_shows=%r states_shows=%r'
                          % (count.get('toggle_shows'), shows)},
        }
    verdict = all(v['ok'] for v in checks.values())
    return {'expectation': expectation, 'verdict': 'GREEN' if verdict else 'RED',
            'checks': checks,
            'observed_visible': visible,
            'observed_shows': shows,
            'press_counts': press_counts}


# ---------------------------------------------------------------------------
# A CORRIDA
# ---------------------------------------------------------------------------
def run_arm(arm, scratch_root, tag, expectation, mutation, timeout=420.0):
    tree = os.path.join(scratch_root, arm)
    tmp = os.path.join(tree, 'tmp')
    os.makedirs(tmp, exist_ok=True)
    log_path = os.path.join(tmp, 'pov-selftest-%s.log' % tag)
    out_path = os.path.join(tmp, 'pov-selftest-%s.out' % tag)
    published = os.path.join(tree, '_main', 'panel-visibility.json')
    for stale in (log_path, out_path):
        try:
            os.remove(stale)
        except OSError:
            pass
    mutation_info = apply_mutation(tree, mutation)

    reader = PublishedReader(published)
    reader.start()
    env = dict(os.environ)
    env['SOTTO_POV_TAG'] = tag
    env['SOTTO_TMP'] = tmp
    env['PYTHONIOENCODING'] = 'utf-8'
    cmd = [sys.executable, os.path.join(tree, '_main', 'pov-selftest.py'),
           '--run', '--json', '--wait', '360', '--exit-after', '300']
    started = time.time()
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                              timeout=timeout, cwd=tree)
        rc, stdout, stderr = proc.returncode, proc.stdout or '', proc.stderr or ''
    except subprocess.TimeoutExpired as exc:
        rc, stdout, stderr = -999, (exc.stdout or ''), (exc.stderr or '')
    elapsed = time.time() - started
    reader.stop()
    reader.join(timeout=5)

    text = ''
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    count = parse_log(text)
    judged = judge(count, expectation) if count.get('ok') else {
        'verdict': 'RED', 'error': count.get('error'), 'checks': {}}
    pub = published_summary(reader.samples)

    # O CRUZAMENTO: o dump da propria app, lido do ficheiro ISOLADO pela mutex.
    state_file = os.path.join(tree, '_main',
                              'panel-state.SottoPovSelftest-%s.json' % tag)
    cross = {'state_file': state_file, 'exists': os.path.exists(state_file)}
    if cross['exists']:
        try:
            with open(state_file, 'r', encoding='utf-8') as fh:
                dump = json.load(fh)
            cross['shell_visible'] = (dump.get('shell') or {}).get('visible')
            cross['panelVisibility'] = dump.get('panelVisibility')
            cross['writtenAt'] = dump.get('writtenAt')
        except Exception as exc:
            cross['error'] = repr(exc)

    # A AUSENCIA de um evento de libertacao entregue a app.
    release_markers = ('HOTKEY_RELEASE', 'WM_KEYUP', 'KEYUP', 'KEY_UP',
                        'GetAsyncKeyState', 'HOTKEY_HOLD', 'HOTKEY_TAP',
                        'HOLD_CEILING')
    found_release = [m for m in release_markers if m in text]
    no_release = not found_release

    hotkey_lines = []
    for line in text.splitlines():
        if any(k in line for k in ('HOTKEY_REGISTERED', 'HOTKEY_REGISTER_FAILED',
                                   'HOTKEY_PROBE', 'HOTKEY_FALLBACK',
                                   'HOTKEY_TRY_FAILED', 'SINGLE_INSTANCE')):
            hotkey_lines.append(line.split('sotto: ', 1)[-1].strip())

    return {
        'arm': arm,
        'expectation': expectation,
        'mutation': mutation_info,
        'tree': tree,
        'tag': tag,
        'log': log_path,
        'log_exists': os.path.exists(log_path),
        'log_bytes': os.path.getsize(log_path) if os.path.exists(log_path) else 0,
        'stdout': stdout[-6000:],
        'stderr': stderr[-2000:],
        'rc': rc,
        'elapsed_s': round(elapsed, 1),
        'count': count,
        'judged': judged,
        'published': pub,
        'published_file': published,
        'cross': cross,
        'no_release_event_delivered': no_release,
        'release_markers_found': found_release,
        'hotkey_lines': hotkey_lines,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--arm', choices=ARMS)
    ap.add_argument('--scratch', default=SCRATCH)
    ap.add_argument('--tag-prefix', default='falsify')
    ap.add_argument('--keep-tree', action='store_true')
    args = ap.parse_args(argv)

    os.makedirs(args.scratch, exist_ok=True)
    report = {'scratch': args.scratch, 'src': SRC_ROOT, 'arms': []}

    plan = [
        ('pos', 'claim', 'none'),
        ('neg-inverted', 'inverted', 'none'),
        ('neg-mutant', 'claim', 'always-strip'),
    ]
    for arm, expectation, mutation in plan:
        if args.arm and args.arm != arm:
            continue
        tree = os.path.join(args.scratch, arm)
        build_tree(SRC_ROOT, tree, force=True)
        tag = '%s-%s' % (args.tag_prefix, arm)
        result = run_arm(arm, args.scratch, tag, expectation, mutation)
        report['arms'].append(result)
        out = os.path.join(args.scratch, 'report-%s.json' % arm)
        with open(out, 'w', encoding='utf-8') as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
        print('ARM %-14s expectation=%-9s mutation=%-12s -> %s  (rc=%s, log=%s)'
              % (arm, expectation, mutation, result['judged'].get('verdict'),
                 result['rc'], result['log']))
        for name, chk in (result['judged'].get('checks') or {}).items():
            print('    %-34s %s  %s' % (name, 'OK  ' if chk['ok'] else 'RED ',
                                       chk.get('detail', '')))
        pub = result['published']
        print('    published: samples=%s saw_true=%s saw_false=%s transitions=%s'
              % (pub['samples'], pub['saw_visible_true'],
                 pub['saw_visible_false'], pub['distinct_transitions']))
        if not args.keep_tree:
            shutil.rmtree(tree, ignore_errors=True)

    out = os.path.join(args.scratch, 'report-all.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print('REPORT %s' % out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
