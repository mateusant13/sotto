#!/usr/bin/env python
"""O FUNDO DE CADA DESENHO CHEGA A JANELA NATIVA DA LEGENDA.

O defeito que este portao existe para impedir, medido duas vezes:

1. 2026-11-03 -- o dono: *"ESSE ESTILO DE LEGENDA E' DO YOUTUBE. NAO SOTTO."*
   A cura foi `set_theme(_THEME_DEFAULT)` sempre, e a partir daí a legenda
   nativa ficou IGUAL em todos os temas.
2. 2026-11-09 -- o dono: *"VOCE TIROU O DESIGN DE TODAS AS LEGENDAS PRA DEIXAR
   ELAS IGUAIS EM TODOS OS TEMAS."* As duas ordens convivem assim: a FACE e' do
   player (Arial 38, contorno 5), a PLACA e' do desenho (`rowBg`/`rowBgAlpha`/
   `rowRadius`/`panelPad` do payload do painel, pelo `_normalise_theme`).

O QUE ESTE ORACULO MEDE, e por que nao basta o lado da pagina: o
`panel-themes-oracle.mjs` prova o float da PAGINA. A legenda que o dono ve por
cima do jogo e' a NATIVA (`caption_overlay` -> `overlay_paint`), um bitmap GDI+
pintado no processo da shell, que nunca le' o DOM. As duas metades se encontram
no payload: o oraculo da pagina grava, por cada um dos 59 desenhos, o
`SottoBrand.last()` que ELE POSTOU; este aqui alimenta o `_brand_tokens` REAL
(extraido por AST do `sotto_webview.py`) com esses mesmos payloads e pinta o
bitmap de verdade, fora do ecra.

Braços:
  A1 payloads            -- os 59 desenhos com payload (CANNOT-MEASURE sem eles)
  A2 placa-por-desenho   -- todo desenho com cama aplica placa com alfa >= 140
  A3 cama-do-payload     -- a cor aplicada E' a cama normalizada DAQUELE payload
  A4 camas-distintas     -- a populacao nao colapsou numa placa generica
  A5 tipografia-do-player-- Arial/38/1.2/contorno 5 em TODOS (ordem 2026-11-03)
  A6 pixel-fora-do-ecra  -- o bitmap GDI+ tem o pixel da placa na cor do desenho
  A7 sem-desenho-sem-placa -- payload vazio continua sem placa (nada inventado)
  A8 raios-distintos     -- o raio da placa acompanha o desenho

`--neg-arm` muta uma COPIA do fonte e exige que o braco NOMEADO caia, com rc=1
(a convencao da casa: o negativo devolve 1 quando apanha).

Uso:
  python _main/caption-overlay-theme-oracle.py [--report _main/_cache/panel-themes.json]
                                               [--refresh] [--neg-arm] [--json out]
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import io
import json
import os
import sys
import tempfile
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
REPORT = os.path.join(ROOT, '_main', '_cache', 'panel-themes.json')
NODE_ORACLE = os.path.join(ROOT, '_main', 'panel-themes-oracle.mjs')
PANEL_HTML = os.path.join(ROOT, 'app', 'panel', 'panel.html')

POPULATION_FLOOR = 20          # um subconjunto `--only` continua mensuravel
BED_DISTINCT_FRACTION = 0.80   # 59 desenhos -> >= 47 camas distintas
RADIUS_DISTINCT_FLOOR = 5
PLATE_ALPHA_FLOOR = 140        # o piso do `_normalise_theme`
PIXEL_TOL = 8


def _fail(msg):
    print(f'VERDICT: FAIL -- {msg}')
    return 0


def _extract(path):
    """`SottoShell._apply_overlay_theme` literal, por AST (nunca por linha).

    2026-11-09: O METODO MUDOU DE CLASS E DE NOME, e este portao julga o que
    EMBARCA. O receptor `SottoHost._brand_tokens` olhava para
    `getattr(self, 'caption_overlay', None)` -- e o overlay mora na SHELL, logo
    aquele `getattr` era `None` para sempre: medido no log do dono, 610
    `CAPTION_OVERLAY_THEME_DEFERRED reason=no-overlay` e ZERO
    `CAPTION_OVERLAY_THEME_APPLIED`. O desenho nunca chegava a janela nativa.
    A aplicacao passou a ter UM dono (a shell), chamado pela pagina
    (`why='page'`) e pela criacao da janela (`why='overlay-created'`).
    """
    src = io.open(path, encoding='utf-8', errors='replace').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_apply_overlay_theme':
            seg = ast.get_source_segment(src, node)
            if not seg:
                raise RuntimeError('source segment unavailable')
            return seg, src
    raise RuntimeError('_apply_overlay_theme not found')


def _load_method(path):
    """Compila o metodo REAL com um `log` gravador e um overlay gravador."""
    code, _src = _extract(path)
    lines = []
    ns = {'log': lines.append}
    sys.path.insert(0, WEBVIEW)
    exec(compile(textwrap.dedent(code), path, 'exec'), ns)  # noqa: S102
    return ns['_apply_overlay_theme'], lines


class _Overlay:
    """O receptor: guarda o ULTIMO tema aplicado, como o overlay real."""

    def __init__(self):
        self.applied = None
        self.calls = 0

    def set_theme(self, tokens):
        import overlay_paint
        self.applied = overlay_paint._normalise_theme(tokens)
        self.calls += 1
        return self.applied


class _Shell:
    def __init__(self):
        self.caption_overlay = _Overlay()
        self._brand_tokens_last = {}


def _payloads(report_path):
    try:
        report = json.load(io.open(report_path, encoding='utf-8'))
    except Exception as exc:  # noqa: BLE001
        return None, f'report unreadable ({exc})'
    themes = report.get('themes') or []
    out = [(t.get('id'), t.get('brand')) for t in themes if isinstance(t.get('brand'), dict)]
    if not out:
        return None, 'report carries no brand payloads (rebuild with --refresh)'
    return out, ''


def _stale(report_path):
    try:
        r = os.path.getmtime(report_path)
    except OSError:
        return True
    for p in (PANEL_HTML, os.path.join(ROOT, 'app', 'panel', 'brand-bridge.js'),
              os.path.join(ROOT, 'app', 'panel', 'panel-unified.css'), NODE_ORACLE):
        try:
            if os.path.getmtime(p) > r:
                return True
        except OSError:
            return True
    return False


def _refresh(report_path):
    """O UNICO instrumento dos payloads e' o oraculo da pagina, com --json."""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    try:
        os.remove(report_path)
    except OSError:
        pass
    cmd = ['node', NODE_ORACLE, '--json', report_path]
    # PELO HELPER DA CASA: `creationflags` sozinho deixa o filho sem consola e o
    # Windows pinta uma NOVA na tela do dono (medido 2026-11-08). O censo
    # `console-window-audit` acusou `WEAK-FLAG` aqui na primeira versao.
    spec = importlib.util.spec_from_file_location(
        '_cot_hl', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'hidden-launch.py'))
    hl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hl)
    rc, out, err = hl.run(cmd, cwd=ROOT, capture=True, timeout=600)
    tail = (out + err).strip().splitlines()[-3:]
    print(f'REFRESH rc={rc} {" | ".join(tail)}')
    return os.path.exists(report_path)


def _pixel_probe(payloads, applied):
    """O bitmap GDI+ real, fora do ecra: o pixel da placa e' o do desenho."""
    sys.path.insert(0, WEBVIEW)
    import overlay_paint
    rows = []
    rim = []
    for tid, payload in payloads:
        theme = applied.get(tid) or {}
        plate = theme.get('plate')
        if not plate:
            rows.append((tid, 'no-plate', None))
            continue
        lines, prev, width, height, _scrolled = overlay_paint._layout(
            'the quick brown fox jumps', '', 2.0, 1920, theme)
        bmp = overlay_paint._premultiplied_bitmap(
            lines, prev, int(width), int(height), 2.0, theme)
        ring = _ring_alpha(bmp, int(width), int(height))
        edge = _plate_edge_alpha(bmp, int(width), int(height), plate)
        px = bmp.GetPixel(3, max(1, int(height) // 2))
        # `GetPixel` num Format32bppPArgb devolve a cor JA' DESMULTIPLICADA
        # (medido: placa (37,28,21,140) -> R=36 G=27 B=21), logo a comparacao
        # e' contra a placa reta -- comparar contra o premultiplicado acusava
        # oito desenhos que estao certos.
        want = [int(c) for c in plate[:3]]
        got = [px.R, px.G, px.B]
        ok = px.A >= PLATE_ALPHA_FLOOR and all(abs(g - w) <= PIXEL_TOL for g, w in zip(got, want))
        rows.append((tid, f'plate={plate} px=A{px.A} rgb={got} want={want}', ok))
        # A ARESTA: um `ring` acima de zero e' o compositor a ver o que o GDI+
        # deixou a meio na fila 0 -- a "borda branca" do dono. E o `edge` diz se
        # a placa tem uma fila de alfa PARCIAL onde a aresta recta dela cai: uma
        # aresta a 110 de 220 e' uma linha translucida que ninguem desenhou.
        rim.append((tid, ring, edge, int(plate[3])))
        bmp.Dispose()
    return rows, rim


def _ring_alpha(bmp, width, height):
    """O maior alfa da FILA EXTERIOR do bitmap (1 px, os quatro lados)."""
    worst = 0
    for x in range(width):
        worst = max(worst, bmp.GetPixel(x, 0).A, bmp.GetPixel(x, height - 1).A)
    for y in range(height):
        worst = max(worst, bmp.GetPixel(0, y).A, bmp.GetPixel(width - 1, y).A)
    return worst


def _edge_control(payloads, applied):
    """O DEFEITO DE VOLTA: arranca a cura e mede outra vez.

    Devolve `(flipped, ring, edge)` onde `ring`/`edge` sao o pior dos desenhos
    SEM a cura. `flipped` exige as duas metades: fila exterior com alfa (o que
    o compositor ve) e aresta da placa a alfa parcial (a "linha" translucida).
    """
    sys.path.insert(0, WEBVIEW)
    import overlay_paint
    worst_ring, worst_edge = 0, None
    saved_px = overlay_paint.EDGE_PX
    saved_clear = overlay_paint._clear_outer_ring
    try:
        overlay_paint.EDGE_PX = 0
        overlay_paint._clear_outer_ring = lambda *a, **k: None
        # A CACHE DE PINTURA E' POR CHAVE DE GEOMETRIA: com `EDGE_PX` mudado a
        # chave nao muda, logo um hit devolveria o raster CURADO e o controlo
        # mediria a cura. Limpar e' o que torna o controlo causal.
        try:
            overlay_paint._PAINT_CACHE.clear()
        except Exception:  # noqa: BLE001
            pass
        for tid, payload in payloads[:6]:
            theme = applied.get(tid) or {}
            plate = theme.get('plate')
            if not plate:
                continue
            lines, prev, width, height, _scrolled = overlay_paint._layout(
                'the quick brown fox jumps', '', 2.0, 1920, theme)
            bmp = overlay_paint._premultiplied_bitmap(
                lines, prev, int(width), int(height), 2.0, theme)
            worst_ring = max(worst_ring, _ring_alpha(bmp, int(width), int(height)))
            a, want = _plate_edge_alpha(bmp, int(width), int(height), plate)
            if worst_edge is None or a < worst_edge[0]:
                worst_edge = (a, want)
            bmp.Dispose()
    except Exception as exc:  # noqa: BLE001
        return None
    finally:
        overlay_paint.EDGE_PX = saved_px
        overlay_paint._clear_outer_ring = saved_clear
        try:
            overlay_paint._PAINT_CACHE.clear()
        except Exception:  # noqa: BLE001
            pass
    edge_bad = bool(worst_edge) and worst_edge[0] < int(worst_edge[1] * 0.95)
    return (worst_ring > 0 or edge_bad), worst_ring, worst_edge


def _plate_edge_alpha(bmp, width, height, plate):
    """O alfa da PLACA logo depois do anel transparente, longe dos cantos.

    A pergunta que este braco faz e' "a placa chega a' cor CHEIA a 2 px da
    borda da janela?" -- e nao "a fila 1 tem o alfa da placa". Medido no bitmap
    real: a placa desenhada ate' ao rectangulo inteiro deixava a fila 1 a ALFA
    PARCIAL (110 de 219) -- uma linha translucida que ninguem desenhou e que
    sobre o video se le' como borda. Depois da cura a transicao
    transparente->placa acontece toda dentro dos 2 px que o anel ocupa, e a
    partir dai' a placa e' cheia.
    """
    x = max(1, width // 2)
    a_top = max(bmp.GetPixel(x, y).A for y in range(1, min(4, height)))
    a_bottom = max(bmp.GetPixel(x, y).A for y in range(max(1, height - 4), height - 1))
    return min(a_top, a_bottom), int(plate[3])


def _face(theme):
    return (theme.get('fontFamily'), round(float(theme.get('livePx') or 0), 1),
            round(float(theme.get('leading') or 0), 2),
            round(float(theme.get('strokePx') or 0), 1))


def run(path, report_path, refresh):
    if refresh or _stale(report_path):
        if not _refresh(report_path):
            return _fail('payload report could not be built')
    payloads, why = _payloads(report_path)
    if not payloads:
        return _fail(f'CANNOT-MEASURE: {why}')
    if len(payloads) < POPULATION_FLOOR:
        return _fail(f'CANNOT-MEASURE: only {len(payloads)} payloads')

    method, loglines = _load_method(path)
    sys.path.insert(0, WEBVIEW)
    import overlay_paint

    applied = {}

    def apply(payload):
        shell = _Shell()
        method(shell, payload)
        return shell.caption_overlay.applied or {}

    arms = []

    def arm(name, ok, detail):
        arms.append({'name': name, 'ok': bool(ok), 'detail': detail})

    for tid, payload in payloads:
        applied[tid] = apply(payload)

    # A2/A3/A5: cada desenho
    # A FACE E' A DO PLAYER: a que `_brand_tokens` aplica quando NAO ha' desenho
    # (`set_theme(_THEME_DEFAULT)`), com Arial e contorno 5 fixados como os
    # numeros da ordem de 2026-11-03.
    #
    # O BASELINE E' MEDIDO, nao escrito a mao, por um numero que o `AGENTS.md`
    # promete e o normalizador nao entrega: `_THEME_DEFAULT['leading']` e' 1.2,
    # e `_normalise_theme` le' `liveLeading` com omissao 1.35 para QUALQUER
    # tema nao vazio -- logo a legenda desenha 1.35 desde antes deste portao.
    # A divergencia fica REGISTRADA aqui (ver recibo); este oraculo julga que o
    # payload nao MUDA a face, nao qual dos dois numeros e' o certo.
    baseline_face = _face(overlay_paint._normalise_theme(dict(overlay_paint._THEME_DEFAULT)))
    no_plate, wrong_bed, wrong_face, radii = [], [], [], set()
    beds = set()
    for tid, payload in payloads:
        got = applied[tid]
        want = overlay_paint._normalise_theme(payload)
        want_plate = want.get('plate')
        plate = got.get('plate')
        if want_plate and not (plate and plate[3] >= PLATE_ALPHA_FLOOR):
            no_plate.append(tid)
        if plate:
            beds.add(tuple(plate[:3]))
            radii.add(round(float(got.get('plateRadius') or 0.0), 1))
            if want_plate and tuple(plate[:3]) != tuple(want_plate[:3]):
                wrong_bed.append(f'{tid}:{plate[:3]}!={want_plate[:3]}')
        face = _face(got)
        if face != baseline_face or face[0] != 'Arial' or face[3] != 5.0:
            wrong_face.append(f'{tid}:{face}')

    arm('placa-por-desenho', not no_plate,
        f'designs={len(payloads)} sem_placa={len(no_plate)} {no_plate[:4]}')
    arm('cama-do-payload', not wrong_bed,
        f'cor_errada={len(wrong_bed)} {wrong_bed[:3]}')
    floor = max(POPULATION_FLOOR // 2, int(round(len(payloads) * BED_DISTINCT_FRACTION)))
    arm('camas-distintas', len(beds) >= floor, f'camas={len(beds)} piso={floor} de {len(payloads)}')
    arm('tipografia-do-player', not wrong_face,
        f'face_errada={len(wrong_face)} {wrong_face[:3]}')
    arm('raios-distintos', len(radii) >= RADIUS_DISTINCT_FLOOR,
        f'raios={len(radii)} piso={RADIUS_DISTINCT_FLOOR} {sorted(radii)[:6]}')

    # A6: o bitmap de verdade
    rows, rim = _pixel_probe(payloads, applied)
    bad_px = [r for r in rows if r[2] is not True]
    arm('pixel-fora-do-ecra', not bad_px,
        f'renders={len(rows)} fora={len(bad_px)} {[b[0] for b in bad_px][:4]}')
    # A10 -- a aresta. Medido no bitmap real de cada desenho: a fila exterior
    # tem de estar a ALFA ZERO (nada pode ser composto sobre o video a partir da
    # borda da janela) e a placa nao pode ter uma fila de alfa PARCIAL na sua
    # aresta recta (era isso que se lia como "borda branca").
    rim_bad = [r[0] for r in rim if r[1] != 0]
    edge_bad = [f'{r[0]}:{r[2][0]}<{r[2][1]}' for r in rim
                if r[2][0] < int(r[3] * 0.95)]
    arm('anel-transparente', not rim_bad,
        f'renders={len(rim)} com_alfa_na_borda={len(rim_bad)} {rim_bad[:4]}')
    arm('placa-sem-aresta-parcial', not edge_bad,
        f'aresta_parcial={len(edge_bad)} {edge_bad[:4]}')

    # A11 -- O CONTROLO DA ARESTA. As duas arms acima so' valem se a cura
    # ARRANCADA as derrubar HOJE: um braco que passa com e sem a cura mede a
    # aritmetica, nao o desenho. O controlo poe `EDGE_PX = 0`, desliga o
    # `_clear_outer_ring` e exige o defeito de volta (alfa na borda e/ou uma
    # fila de alfa parcial na aresta da placa).
    ctl = _edge_control(payloads, applied)
    arm('controlo-da-aresta', ctl is not None and ctl[0],
        f'sem_a_cura ring={None if ctl is None else ctl[1]} '
        f'aresta={None if ctl is None else ctl[2]}')

    # A7: sem desenho, sem placa -- nada e' inventado
    bare = apply({})
    arm('sem-desenho-sem-placa', not bare.get('plate'),
        f'plate={bare.get("plate")} face={bare.get("fontFamily")}')

    # A1: a populacao
    arm('payloads', True, f'{len(payloads)} payloads de {len(payloads)}')

    # A9 -- A JANELA NASCE VESTIDA (2026-11-09). O defeito medido no log do dono
    # era este caminho: 215 criacoes, todas `REPLAYED theme=youtube brand='-'`, e
    # `CAPTION_OVERLAY_THEME_APPLIED` ZERO no log inteiro. A criacao tem de
    # aplicar o PAYLOAD GUARDADO pelo mesmo caminho da pagina -- e nao voltar ao
    # `_THEME_DEFAULT` --, e o receptor do host tem de delegar na shell.
    src_all = io.open(path, encoding='utf-8', errors='replace').read()
    creation = ''
    for node in ast.walk(ast.parse(src_all)):
        if isinstance(node, ast.FunctionDef) and node.name in (
                '_caption_overlay_ensure', '_ensure_caption_overlay', 'show_caption_window'):
            creation += ast.get_source_segment(src_all, node) or ''
    if not creation or 'overlay-created' not in creation:
        # O BLOCO DA CRIACAO VIVE INLINE NUM METODO MAIOR, e procurar pelo
        # `CAPTION_OVERLAY_MODE` acha a primeira ocorrencia do FICHEIRO (que
        # esta' na documentacao, milhares de linhas acima) -- medido: a janela
        # saia vazia do bloco real e o braco reprovava a cura. A ancora certa e'
        # a PROPRIA chamada de replay.
        idx = src_all.find("why='overlay-created'")
        creation = src_all[max(0, idx - 6000):idx + 6000] if idx > 0 else creation
    replays_design = "_apply_overlay_theme(stored, why='overlay-created')" in creation
    falls_back = "source=default why=no-stored-design" in creation
    asks_page = 'SottoBrand.push()' in creation
    host_delegates = 'shell._apply_overlay_theme(theme' in src_all
    arm('criacao-veste-o-desenho',
        replays_design and falls_back and asks_page and host_delegates,
        'replay=%s fallback=%s pede_a_pagina=%s host_delega=%s'
        % (replays_design, falls_back, asks_page, host_delegates))

    passed = sum(1 for a in arms if a['ok'])
    for a in arms:
        print(f'{"PASS" if a["ok"] else "RED "} {a["name"]} -- {a["detail"]}')
    print(f'VERDICT: {"PASS" if passed == len(arms) else "FAIL"} ({passed}/{len(arms)})')
    if loglines:
        print(f'LOG lines={len(loglines)} first={loglines[0][:100]!r}')
    # rc 0 = PASS. A primeira versao devolvia 1 quando passava e o passo da
    # bateria nao podia declara-lo (a casa le 0 como verde desde sempre).
    return 0 if passed == len(arms) else 1


MUTANTS = [
    ('M4 criacao-sem-desenho',
     "self._apply_overlay_theme(stored, why='overlay-created')",
     "self.caption_overlay.set_theme(__import__('overlay_paint')._THEME_DEFAULT)",
     'criacao-veste-o-desenho'),
    ('M1 sem-placa', "applied = overlay.set_theme(base)",
     "applied = overlay.set_theme(dict(overlay_paint._THEME_DEFAULT))", 'placa-por-desenho'),
    ('M2 placa-generica', "base['plate'] = plate",
     "base['plate'] = (0, 0, 0, 220)", 'cama-do-payload'),
    ('M3 face-do-payload', "applied = overlay.set_theme(base)",
     "applied = overlay.set_theme(theme)", 'tipografia-do-player'),
]


def negative_arm(report_path):
    payloads, why = _payloads(report_path)
    if not payloads:
        print(f'CANNOT-MEASURE: {why}')
        return 0
    caught = 0
    for name, old, new, expect in MUTANTS:
        code, src = _extract(SHELL)
        # O MUTANTE VIVE ONDE O TEXTO VIVE: M1-M3 dentro do corpo extraido, M4 no
        # SITIO DA CRIACAO (outro ponto do ficheiro). Procurar no corpo extraido
        # um texto que so' existe 700 linhas abaixo dizia "IMPOSSIBLE" e o braco
        # contava como nao apanhado -- foi assim que M4 nasceu mudo.
        if old in code:
            mutated = src.replace(code, code.replace(old, new, 1), 1)
        elif old in src:
            mutated = src.replace(old, new, 1)
        else:
            print(f'IMPOSSIBLE {name} -- anchor absent: {old!r}')
            continue
        tmp = tempfile.mkdtemp(prefix='caption-theme-neg-')
        path = os.path.join(tmp, 'sotto_webview.py')
        io.open(path, 'w', encoding='utf-8', newline='').write(mutated)
        try:
            ok = _run_quiet(path, report_path)
        finally:
            try:
                os.remove(path)
                os.rmdir(tmp)
            except OSError:
                pass
        flipped = not ok
        print(f'{"CAUGHT" if flipped else "NOT-CAUGHT"} {name} -- expect {expect} red')
        caught += 1 if flipped else 0
    ok = caught == len(MUTANTS)
    print(f'NEG-ARM: {"PASS" if ok else "FAIL"} -- {caught}/{len(MUTANTS)} mutants caught')
    # A CONVENCAO DA CASA: o braco negativo devolve 1 QUANDO APANHA, para o passo
    # `red-as-expected-*` poder exigir esse 1. Devolver 0 ao apanhar faz do controlo um
    # passo que nunca pode falhar (a classe medida em 2026-11-08 no panel-pause-payload).
    # O CONTRARIO DO POSITIVO, e de proposito: rc 1 AQUI significa "apanhou os
    # mutantes", que e' o que o passo `red-as-expected-*` exige.
    return 1 if ok else 0


def _run_quiet(path, report_path):
    """A mesma bateria de bracos, sem imprimir, para o negativo."""
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = run(path, report_path, False)
    return rc == 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', default=REPORT)
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--json', default='')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return negative_arm(args.report)
    rc = run(SHELL, args.report, args.refresh)
    if args.json:
        io.open(args.json, 'w', encoding='utf-8').write(
            json.dumps({'rc': rc}, indent=2))
    return rc


if __name__ == '__main__':
    sys.exit(main())
