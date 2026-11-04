"""O show REAL do dono: a janela foi mapeada DEPOIS de o conteudo ser aplicado?

Duas perguntas, uma so' linha de log cada, porque a ordem e' o defeito:

  * `PANEL_CONTENT ack=true ... order=before-map` -- o shell perguntou a' pagina,
    ANTES do mapa, se a superficie ja' estava vestida (estilo recalculado e
    layout forçado por `getBoundingClientRect`); `ack=true` quer dizer que o
    `body[data-surface]` que o `ShowWindow` vai apresentar ja' era o pedido e o
    estilo dessa superficie ja' estava computado.
  * `PANEL_SHOWN ... content_ack=true content_wait_ms=.. paint_ack=.. wait_ms=..`
    -- o mapa e a frame.

O oraculo julga a ORDEM: cada `PANEL_SHOWN` tem de ter, ANTES dele na sessao
viva, o `PANEL_CONTENT` que o informou, com `ack=true`. Um log em que o show
aparece primeiro e' literalmente a queixa do dono -- *"o painel dar show, nao
deve carregar o background e mostrar, e depois carregar a ui"* -- e o braco
negativo muta exactamente isso.

Regras herdadas de 2026-11-01, sem alteracao:

  * a sessao viva comeca na ULTIMA linha `SHELL_STARTUP_STAGE` (ou `SHELL_START`);
  * `PAINT_WARM ... ack=true` tem de existir nessa sessao quando houve show;
  * todo `PANEL_SHOWN` traz `paint_ack=true` e `wait_ms <= 400` (o tecto e' o
    `PAINT_ACK_TIMEOUT_MS` do shell).

SEM SHOW NA SESSAO NAO E' VERDE: imprime `VERDICT: SKIPPED` com a hora do
arranque, e o passo skip-capable da bateria conta o como SKIPPED -- um passo
saltado nunca e' um portao que passou.

O QUE ELE NAO PROVA: pixel. Quem mede pixel e' `_main/panel-paint-first-census.py`,
numa instancia privada; este le a instancia que o dono carrega, e a lei
`SOTTO_NEVER_ON_OWNER_SCREEN` proibe uma lane de a pôr no ecra dele.

Efervescencia: `--neg-arm` muta uma copia do log em CINCO pontos e o FONTE do
shell em um (mapa antes do gate), e exige os seis vermelhos.
"""
# NO-BUG: instrumento do show REAL: exige `PANEL_CONTENT ack=true` ANTES de cada `PANEL_SHOWN`, mais `content_ack=true`, `paint_ack=true` e `wait_ms<=400`; diz SKIPPED quando ainda nao houve show
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, 'webview-run.log')
SOURCE = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
ACK_MAX_MS = 400.0
#: O orcamento do gate e' `CONTENT_GATE_TIMEOUT_MS` = 250 ms; o fio de cabelo a
#: mais e' o poll e o marshalling, nao uma segunda espera.
CONTENT_MAX_MS = 350.0

_START = ('SHELL_STARTUP_STAGE', 'SHELL_START')
_WARM = 'PAINT_WARM'
_CONTENT = 'PANEL_CONTENT'
_SHOWN = 'PANEL_SHOWN'


def _lines(text):
    return [ln for ln in text.splitlines() if ln.strip()]


def _stamp(line):
    m = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})', line)
    return m.group(1) if m else ''


def _get(line, key):
    m = re.search(r'\b%s=(\S+)' % (re.escape(key),), line)
    return m.group(1) if m else None


def _ms(line, key):
    try:
        return float(_get(line, key))
    except (TypeError, ValueError):
        return None


def _session(lines):
    """A ULTIMA sessao viva: tudo depois do ultimo arranque de shell."""
    start_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if any(tag in lines[i] for tag in _START):
            start_idx = i
            break
    if start_idx is None:
        return None
    return lines[start_idx:]


def judge(text):
    """-> (verdict, detail). `verdict` in GREEN | RED | SKIPPED. Puro: so' o texto."""
    lines = _lines(text)
    session = _session(lines)
    if session is None:
        return 'SKIPPED', {'why': 'nenhum arranque de shell no log -- nao ha sessao viva a julgar',
                           'shows': 0}
    warm = [ln for ln in session if _WARM in ln]
    warm_ok = [ln for ln in warm if (_get(ln, 'ack') or '') == 'true']
    shown_idx = [i for i, ln in enumerate(session) if _SHOWN in ln]
    content_idx = [i for i, ln in enumerate(session) if _CONTENT in ln]
    detail = {'started': _stamp(session[0]), 'warm': len(warm),
              'warm_ack': len(warm_ok), 'shows': len(shown_idx),
              'content': len(content_idx), 'content_ack': 0,
              'shows_verbatim': [], 'fails': []}
    for i in shown_idx:
        detail['shows_verbatim'].append(session[i])
    # UM SHOW QUE NUNCA ACONTECEU NAO TEM CAMINHO. `PAINT_WARM` existe para o
    # PRIMEIRO show nao cair no caminho frio; uma sessao que nunca mostrou o
    # painel (uma lane, uma sessao `--no-self-relaunch`, o dono sem Alt+C) nao
    # deve nada ao caminho quente. Medido 2026-11-04: um arranque de lane sem
    # show nenhum publicava RED "o show cai no caminho frio" -- um vermelho sobre
    # um passo que nao correu. So' se exige o warm quando houve show para julgar.
    if shown_idx and not warm:
        detail['fails'].append('a sessao viva nao tem PAINT_WARM: o show cai no caminho frio')
    elif shown_idx and not warm_ok:
        detail['fails'].append('PAINT_WARM existe mas sem ack=true (%s)'
                               % (_get(warm[-1], 'ack'),))
    # O CONTEUDO DE CADA GATE, e depois a ORDEM dele contra o mapa.
    content_ok = []
    for j in content_idx:
        ack = (_get(session[j], 'ack') or '')
        if ack == 'true':
            content_ok.append(j)
        else:
            detail['fails'].append(
                'conteudo nao aplicado antes do mapa (%s): ack=%s why=%s -- o show '
                'segue pela falha aberta, e o artefacto diz que ele seguiu'
                % (_stamp(session[j]) or '?', ack, _get(session[j], 'why')))
    detail['content_ack'] = len(content_ok)
    bad = []
    waits, cwaits = [], []
    for i in shown_idx:
        ln = session[i]
        ack = _get(ln, 'content_ack')
        cack = _get(ln, 'content_wait_ms')
        cms = _ms(ln, 'content_wait_ms')
        if cms is not None:
            cwaits.append(cms)
        before = [j for j in content_ok if j < i]
        if ack != 'true':
            bad.append((ln, 'content_ack=%s (o mapa nao esperou o conteudo)' % (ack,)))
        elif not before:
            # A ORDEM E' O DEFEITO. Um show sem um `PANEL_CONTENT ack=true`
            # ANTES dele e' a janela a aparecer antes da UI.
            bad.append((ln, 'nenhum PANEL_CONTENT ack=true ANTES do show '
                            '(a janela foi mapeada antes do conteudo)'))
        elif cms is None:
            bad.append((ln, 'sem content_wait_ms'))
        elif cms > CONTENT_MAX_MS:
            bad.append((ln, 'content_wait_ms=%.1f > %.0f' % (cms, CONTENT_MAX_MS)))
        pack = _get(ln, 'paint_ack')
        ms = _ms(ln, 'wait_ms')
        if ms is not None:
            waits.append(ms)
        if pack != 'true':
            bad.append((ln, 'paint_ack=%s' % (pack,)))
        elif ms is None:
            bad.append((ln, 'sem wait_ms'))
        elif ms > ACK_MAX_MS:
            bad.append((ln, 'wait_ms=%.1f > %.0f' % (ms, ACK_MAX_MS)))
    detail['max_wait_ms'] = max(waits) if waits else None
    detail['max_content_wait_ms'] = max(cwaits) if cwaits else None
    for ln, why in bad:
        detail['fails'].append('show %s: %s' % (_stamp(ln) or '?', why))
    if detail['fails']:
        return 'RED', detail
    if not shown_idx:
        return 'SKIPPED', dict(detail, why='nenhum Alt+C nesta sessao ainda (%s) -- nada a julgar'
                               % (detail['started'] or 'sem hora',))
    return 'GREEN', detail


# ── O FONTE: A ORDEM TAMBEM SE LE' NO CODIGO ────────────────────────────────
#: As tres funcoes que mapeiam o painel, e o token do mapa de cada uma. O gate
#: tem de aparecer ANTES do mapa no corpo da funcao: um mutante que troca as
#: duas linhas e' "mostrar a janela antes do conteudo ser aplicado" no proprio
#: ficheiro que a app carrega, e o log de uma instancia antiga nao o mostraria.
_SOURCE_PATHS = (
    ('show_panel', 'show_without_activating(self.hwnd)'),
    ('show_strip', 'fg = foreground_unlock(self.hwnd)'),
    ('show_side', 'fg = foreground_unlock(self.hwnd)'),
)
_GATE_CALL = 'content_gate('


def judge_source(src):
    """-> lista de falhas (vazia = ordem certa). Puro: so' o texto do fonte."""
    fails = []
    for name, map_call in _SOURCE_PATHS:
        m = re.search(r'\n    def %s\(self[^\n]*\n(.*?)(?=\n    def )' % (re.escape(name),),
                      src, re.S)
        if not m:
            fails.append('%s: funcao nao encontrada no fonte' % (name,))
            continue
        body = m.group(1)
        gate_at = body.find(_GATE_CALL)
        map_at = body.find(map_call)
        if gate_at < 0:
            fails.append('%s: sem `%s` -- o mapa nao pergunta nada a\' pagina'
                         % (name, _GATE_CALL.strip('(')))
        elif map_at < 0:
            fails.append('%s: sem o mapa `%s` -- o instrumento nao sabe o que julgar'
                         % (name, map_call))
        elif gate_at > map_at:
            fails.append('%s: o mapa (`%s`) vem ANTES do gate -- a janela aparece '
                         'antes do conteudo' % (name, map_call))
    return fails


# ── AS MUTACOES ─────────────────────────────────────────────────────────────
def _last_eq_off(key):
    def mutate(text):
        at = text.rfind('%s=true' % (key,))
        if at < 0:
            return text
        return text[:at] + '%s=false' % (key,) + text[at + len(key) + 5:]
    return mutate


def _content_ack_off(text):
    """Desliga o `ack` da ULTIMA linha `PANEL_CONTENT` -- o campo que o gate le."""
    lines = text.splitlines()
    ci = [i for i, ln in enumerate(lines) if _CONTENT in ln]
    if not ci:
        return text
    at = ci[-1]
    lines[at] = re.sub(r'\back=true\b', 'ack=false', lines[at], count=1)
    return '\n'.join(lines) + ('\n' if text.endswith('\n') else '')


def _map_before_content(text):
    """Empurra o ULTIMO `PANEL_CONTENT` para DEPOIS do ultimo `PANEL_SHOWN`."""
    lines = text.splitlines()
    ci = [i for i, ln in enumerate(lines) if _CONTENT in ln]
    si = [i for i, ln in enumerate(lines) if _SHOWN in ln]
    if not ci or not si:
        return text
    line = lines.pop(ci[-1])
    after = max(i for i, ln in enumerate(lines) if _SHOWN in ln)
    lines.insert(after + 1, line)
    return '\n'.join(lines) + '\n'


def _source_map_first(src):
    """Troca, em cada funcao do mapa, o gate e a linha do mapa de lugar."""
    out = []
    for chunk in re.split(r'(?=\n    def )', src):
        name = chunk.lstrip('\n').split('\n', 1)[0].strip()
        swapped = chunk
        for fname, map_call in _SOURCE_PATHS:
            if name.startswith('def %s(' % (fname,)):
                gate_line = '        content = self.content_gate(reason, self.surface_applied)\n'
                map_line = '        %s\n' % (map_call,)
                if gate_line in swapped and map_line in swapped:
                    # MOVE, nao troca: o gate sai do lugar e entra DEPOIS do
                    # mapa -- o mutante e' "a janela primeiro", com o
                    # comentario e a distancia que o ficheiro real tem.
                    swapped = swapped.replace(gate_line, '', 1)
                    swapped = swapped.replace(map_line, map_line + gate_line, 1)
        out.append(swapped)
    return ''.join(out)


NEG_CASES = (
    # (rotulo, o que muda, o que se espera)
    # A ULTIMA, NAO A PRIMEIRA (medido 2026-11-02): `replace(..., 1)` mutava o
    # `PANEL_SHOWN` de uma sessao ANTERIOR e o julgar so le a sessao viva -- a
    # mutacao nao movia o artefacto do veredicto e o braco publicava NOT-CAUGHT
    # (cases=3 caught=2). A licao ja' estava no `show-lento` ao lado.
    ('show-sem-ack', _last_eq_off('paint_ack'), 'RED'),
    # O MUTANTE DA ORDEM: o mapa primeiro, o conteudo depois. E' a queixa do
    # dono escrita num log.
    ('mapa-antes-do-conteudo', _map_before_content, 'RED'),
    ('show-sem-ack-conteudo', _last_eq_off('content_ack'), 'RED'),
    ('conteudo-nao-aplicado', _content_ack_off, 'RED'),
    # A cauda sintetica e' a ULTIMA ocorrencia: mutar a primeira apanhava uma sessao velha
    # e o braco passava verde (medido).
    ('show-lento', lambda t: re.sub(r'wait_ms=[\d.]+(?=[^\d.]*$)', 'wait_ms=951.0', t), 'RED'),
    ('sessao-sem-aquecimento', lambda t: '\n'.join(
        ln for ln in t.splitlines() if _WARM not in ln), 'RED'),
)


def neg_arm(text, source_text=None):
    cases = list(NEG_CASES)
    bad = 0
    for label, mutate, expect in cases:
        got, detail = judge(mutate(text))
        ok = got == expect
        bad += 0 if ok else 1
        print('  %-28s -> %-8s %s  %s'
              % (label, got, 'RED-as-required' if ok else 'NOT-CAUGHT',
                 (detail.get('fails') or ['-'])[0][:90]))
    # O MUTANTE DO FONTE, ao lado dos do log: a ordem no ficheiro que a app
    # carrega, nao so' na linha que ele escreveu.
    if source_text:
        fails = judge_source(_source_map_first(source_text))
        ok = bool(fails)
        bad += 0 if ok else 1
        print('  %-28s -> %-8s %s  %s'
              % ('fonte-mapa-antes-do-gate', 'RED' if ok else 'GREEN',
                 'RED-as-required' if ok else 'NOT-CAUGHT',
                 (fails or ['o mutante passou -- o instrumento nao le a ordem'])[0][:90]))
        real_fails = judge_source(_REAL_SOURCE) if _REAL_SOURCE else ['fonte real ausente']
        print('POSITIVE-CONTROL: o fonte REAL tem a ordem certa? '
              '%s%s' % ('sim' if not real_fails else 'NAO -- o braco nao mede nada',
                        '' if not real_fails else '  %s' % (real_fails[0][:80],)))
    if not text.strip():
        print('NEG-ARM: a amostra esta vazia -- as mutacoes nao provam nada')
        return 1
    total = len(cases) + (1 if source_text else 0)
    print('NEG-ARM cases=%d caught=%d' % (total, total - bad))
    if bad:
        print('NEG-ARM FAIL')
        return 2
    print('NEG-ARM PASS')
    return 1   # convencao da casa: o braco negativo PASSOU sai rc=1 e o passo e' expect-red


_REAL_SOURCE = ''


def main(argv=None):
    global _REAL_SOURCE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--log', default=LOG)
    ap.add_argument('--source', default=SOURCE)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    source_text = ''
    if os.path.exists(args.source):
        source_text = open(args.source, encoding='utf-8', errors='replace').read()
        _REAL_SOURCE = source_text
    # O FONTE E' JULGADO SEMPRE: o log pode nao ter um show ainda, mas a ordem no
    # codigo que ele vai carregar ja' e' uma pergunta com resposta.
    src_fails = judge_source(source_text) if source_text else ['fonte ausente em %s' % (args.source,)]
    if not os.path.exists(args.log):
        print('PAINT-LIVE VERDICT: SKIPPED (sem log em %s)' % (args.log,))
        return 0
    text = open(args.log, encoding='utf-8', errors='replace').read()
    if args.neg_arm:
        # A amostra das mutacoes e' o log REAL; se ele nao tem um show ainda, fabrica-se um
        # a partir do arranque, porque um braco negativo sobre texto vazio e' um braco a rir.
        # SEMPRE uma cauda sintetica LIMPA: as mutacoes tem de morder alguma coisa, e o
        # texto vivo pode nao ter show nenhum (foi o caso medido hoje). O braco positivo
        # deste oraculo continua a ser o log REAL (`--log`), nunca esta cauda.
        sample = (text + '\n2099-01-01 00:00:00.000 sotto: PAINT_WARM reason=startup ack=true'
                         ' ack_wait_ms=31.0\n'
                         '2099-01-01 00:00:01.000 sotto: PANEL_CONTENT surface=strip ack=true'
                         ' applied="strip" style=true sized=true size=1040x150 head="none"'
                         ' vis=visible wait_ms=9.0 why=applied order=before-map'
                         ' reason=hotkey-cycle-strip timeout_ms=250.0\n'
                         '2099-01-01 00:00:01.030 sotto: PANEL_SHOWN reason=hotkey-cycle-strip'
                         ' mode=strip visible=true paint_ack=true content_ack=true'
                         ' content_wait_ms=9.0 wait_ms=32.0\n')
        return neg_arm(sample, source_text or None)
    verdict, detail = judge(text)
    print('PAINT-LIVE arranque=%s warm=%d ack=%d conteudo=%d conteudo_ack=%d shows=%d '
          'max_wait_ms=%s max_content_wait_ms=%s'
          % (detail.get('started') or '-', detail.get('warm', 0),
             detail.get('warm_ack', 0), detail.get('content', 0),
             detail.get('content_ack', 0), detail.get('shows', 0),
             detail.get('max_wait_ms'), detail.get('max_content_wait_ms')))
    shows = detail.get('shows_verbatim') or []
    if shows:
        print('PAINT-LIVE shows (verbatim, sessao viva):')
        for ln in shows:
            print('  %s' % (ln,))
    else:
        # A SESSAO VIVA AINDA NAO TEM SHOW. As ultimas linhas do log sao de uma
        # sessao ANTERIOR e nao entram no veredicto; ficam impressas porque sao a
        # unica evidencia de show que o ficheiro tem hoje.
        old = [ln for ln in _lines(text) if _SHOWN in ln][-3:]
        for ln in old:
            print('PAINT-LIVE show (verbatim, FORA da sessao viva): %s' % (ln,))
    for why in src_fails:
        print('  RED (fonte): %s' % (why,))
    for why in detail.get('fails') or []:
        print('  RED: %s' % (why,))
    if src_fails:
        print('PAINT-LIVE VERDICT: RED')
        return 1
    if verdict == 'SKIPPED':
        print('PAINT-LIVE VERDICT: SKIPPED (%s)'
              % (detail.get('why') or 'nada a julgar',))
        return 0
    print('PAINT-LIVE VERDICT: %s' % (verdict,))
    return 0 if verdict == 'GREEN' else 1


if __name__ == '__main__':
    raise SystemExit(main())
