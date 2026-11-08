#!/usr/bin/env python
"""Sotto -- o PORTAO DA IDENTIDADE: cada tema tem o SEU desenho de legenda.

NASCEU DE UMA ORDEM DO DONO (2026-11-08, verbatim):

    "MEU DEUS, QUE NOJO QUE VOCE ME DA. VOCE TIROU O DESIGN DE TODAS AS LEGENDAS
     PRA DEIXAR ELAS IGUAIS EM TODOS OS TEMAS."

E ela estava CERTA, medivelmente: a cura de legibilidade do historico tinha posto
`font-family: "Instrument Sans"`, `font-size: calc(13.5px * var(--caption-scale))`
e `line-height: 1.5` como LITERAIS com `!important` em
`app/panel/panel-unified.css` -- o ultimo ficheiro que o `panel.html` carrega --,
sobre TODOS os 45 desenhos. Cada tema define `--font-sans`, `--size-caption`
(theme-1 18.5px .. theme-2 10.5px), `--leading-caption`, `--weight-caption`,
`--tracking-caption` e `--caption-upper`, e nenhum deles chegava a linha.

O QUE ESTE PORTAO JULGA (cada braco com o seu numero):

  A1  A UNIAO. Todo id que embarca (as cinco direcoes base, as 25 do cinemático,
      as 5 do `panel-designs`) define os SEIS tokens que a linha le'. Um tema que
      nao os defina nao tem identidade a perder -- ele herda a de outro.
  A2  ZERO LITERAL DE DESENHO no bloco do historico: familia, tamanho,
      entrelinha, peso, espacamento e caixa tem de vir por `var(--...)`. E' o
      defeito do dono, escrito como assercao.
  A3  IDENTIDADE OBSERVAVEL: resolvidos os `var()` com os tokens de cada tema,
      os cinco desenhos base produzem pelo menos QUATRO tamanhos distintos e as
      35 direcoes produzem pelo menos DEZ tuplas distintas (familia, tamanho,
      espacamento, caixa).
  A4  O PISO DE LEGIBILIDADE fica: nenhum tamanho resolvido abaixo de 13.5px no
      dial default (era 9 px em theme-2 antes da cura, e o dono chamou isso de
      "patetico").
  A5  A COR continua a vir do tema (`--text-primary`), nao de um literal.

BRAÇO NEGATIVO (`--neg-arm`): tres mutacoes, cada uma numa COPIA do ficheiro
real, e o braco que a possui TEM de ficar vermelho --
  M1  os literais de volta (familia + tamanho + entrelinha) -> A2 e A3 caem;
  M2  o piso arrancado (`max(13.5px, ...)` -> `var(...)`) com `--size-caption`
      de theme-2 -> A4 cai;
  M3  a cor trocada por um literal -> A5 cai.
O `--neg-arm` devolve rc=1 quando apanha os mutantes (a convencao da casa).

Run:  python _main/theme-caption-identity-oracle.py
      python _main/theme-caption-identity-oracle.py --neg-arm
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

UNIFIED = os.path.join(ROOT, 'app', 'panel', 'panel-unified.css')
THEMES = [
    ('app/panel/themes/theme-1.css', r"data-theme=['\"]([a-z0-9-]+)['\"]"),
    ('app/panel/themes/theme-2.css', r"data-theme=['\"]([a-z0-9-]+)['\"]"),
    ('app/panel/themes/theme-3.css', r"data-theme=['\"]([a-z0-9-]+)['\"]"),
    ('app/panel/themes/theme-4.css', r"data-theme=['\"]([a-z0-9-]+)['\"]"),
    ('app/panel/themes/theme-5.css', r"data-theme=['\"]([a-z0-9-]+)['\"]"),
    ('app/panel/themes/cinematic.css', r"data-theme=['\"]([a-z0-9-]+)['\"]"),
    ('app/panel/themes/panel-designs.css', r"data-theme=['\"]([a-z0-9-]+)['\"]"),
]

#: Os tokens que a linha do historico consome. Um tema sem eles nao tem desenho
#: proprio nesta peca -- ele herda o de quem os definir por ultimo.
TOKENS = ('--font-sans', '--size-caption', '--leading-caption',
          '--weight-caption', '--tracking-caption', '--caption-upper')

#: O piso de legibilidade. E' numero, nao gosto: 9 px foi o defeito medido e
#: 13.5 px foi a cura que o dono aceitou.
FLOOR_PX = 13.5

#: O bloco que carrega o desenho do historico.
BLOCK_RE = re.compile(
    r'html body\[data-surface="panel"\] \.history__list \.hist__text\s*\{(.*?)\}',
    re.S)
SEL_TEXT = 'html body[data-surface="panel"] .history__list .hist__text'

DESIGN_PROPS = ('font-family', 'font-size', 'line-height', 'font-weight',
                'letter-spacing', 'text-transform')


def read(path):
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def declarations(body):
    """'prop: value' pairs of a declaration block, whitespace collapsed."""
    out = {}
    for part in strip_comments(body).split(';'):
        if ':' not in part:
            continue
        key, value = part.split(':', 1)
        out[key.strip()] = ' '.join(value.split())
    return out


def hist_block(css):
    """EVERY block for that selector, in document order, as one body.

    A mesma seletor aparece mais de uma vez na folha (a cor numa regra, o desenho
    noutra); ler so' o primeiro bloco faz o juiz medir metade da regra e reprovar
    por ausencia. As declaracoes sao concatenadas e `declarations()` deixa a
    ULTIMA ganhar -- que e' como o navegador resolve mesma especificidade.
    """
    blocks = BLOCK_RE.findall(strip_comments(css))
    return ';'.join(blocks)


def theme_tokens(css):
    """{theme id: {token: value}} for every `:root[data-theme='X']` block."""
    css = strip_comments(css)
    ids = re.findall(r":root\[data-theme=['\"]([a-z0-9-]+)['\"]\]", css)
    out = {}
    for tid in dict.fromkeys(ids):
        # every block for that theme; later declarations win, which is how the
        # cascade resolves same-specificity rules in document order
        blocks = re.findall(
            r":root\[data-theme=['\"]%s['\"]\][^{]*\{(.*?)\}" % re.escape(tid),
            css, re.S)
        vals = {}
        for body in blocks:
            for key, value in declarations(body).items():
                if key in TOKENS:
                    vals[key] = value
        out[tid] = vals
    return out


def collect_themes():
    themes = {}
    for rel, _ in THEMES:
        path = os.path.join(ROOT, rel)
        themes.update(theme_tokens(read(path)))
    return themes


def px(value):
    m = re.match(r'^\s*([0-9.]+)\s*px\s*$', value or '')
    return float(m.group(1)) if m else None


def resolve_size(decl, tokens):
    """The declared font-size, resolved for one theme. `max(FLOOR, var(--size-caption))`
    is evaluated here; anything else is reported unresolved (and fails A2 first)."""
    value = decl.get('font-size', '')
    inner = re.search(r'max\(\s*([0-9.]+)px\s*,\s*var\((--[a-z-]+)', value)
    if inner:
        floor = float(inner.group(1))
        own = px(tokens.get(inner.group(2), ''))
        return max(floor, own) if own is not None else floor
    simple = re.search(r'var\((--[a-z-]+)', value)
    if simple:
        return px(tokens.get(simple.group(1), ''))
    return px(re.sub(r'^calc\((.*)\*.*$', r'\1', value))


def judge(unified_css, themes):
    """The five arms. Returns [(name, ok, detail)]."""
    decl = declarations(hist_block(unified_css))
    arms = []

    # A1 -- every shipped theme has the six tokens
    missing = []
    for tid, tokens in themes.items():
        gaps = [t for t in TOKENS if t not in tokens]
        if gaps:
            missing.append('%s:%s' % (tid, ','.join(gaps)))
    arms.append(('A1 uniao', not missing,
                 'desenhos=%d sem_tokens=%d %s' % (
                     len(themes), len(missing), missing[:4])))

    # A2 -- no literal design value; every design property goes through var()
    literal = [p for p in DESIGN_PROPS
               if p in decl and 'var(--' not in decl[p]]
    missing_props = [p for p in DESIGN_PROPS if p not in decl]
    arms.append(('A2 zero literal', not literal and not missing_props,
                 'literais=%r ausentes=%r' % (literal, missing_props)))

    # A3 -- observable identity
    base = [t for t in ('theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5')
            if t in themes]
    sizes = {t: resolve_size(decl, themes[t]) for t in base}
    distinct_sizes = {s for s in sizes.values() if s is not None}
    tuples = set()
    for tid, tokens in themes.items():
        size = resolve_size(decl, tokens)
        tuples.add((tokens.get('--font-sans'), size,
                    tokens.get('--tracking-caption'), tokens.get('--caption-upper')))
    arms.append(('A3 identidade', len(distinct_sizes) >= 4 and len(tuples) >= 10,
                 'tamanhos_base=%s distintas=%d tuplas=%d' % (
                     {k: v for k, v in sizes.items()}, len(distinct_sizes),
                     len(tuples))))

    # A4 -- the legibility floor
    below = {t: s for t, s in sizes.items() if s is not None and s < FLOOR_PX}
    arms.append(('A4 piso', not below,
                 'abaixo_de_%.1fpx=%r' % (FLOOR_PX, below)))

    # A5 -- the colour is the theme's
    colour = decl.get('color', '')
    arms.append(('A5 cor do tema', 'var(--text-primary' in colour or
                 'var(--text' in colour, 'color=%r' % colour))
    return arms


def mutate(css, which):
    """One property of the real SHEET turned into the defect the gate guards.

    A mutacao trabalha no TEXTO do ficheiro (cada bloco da seletor, um a um), e
    nao na string concatenada que `hist_block` devolve: aquela nao existe no
    disco, logo um `replace` sobre ela devolve o ficheiro intacto e o braco
    negativo "passa" sem tocar em nada -- medido, 0/4 antes desta correcao.
    """
    pattern = re.compile(
        r'(html body\[data-surface="panel"\] \.history__list \.hist__text\s*\{)'
        r'(.*?)(\})', re.S)

    def each(match):
        head, body, tail = match.group(1), match.group(2), match.group(3)
        if which == 'M1':
            for prop, literal in (
                    ('font-family', '"Instrument Sans", "Segoe UI", sans-serif !important'),
                    ('font-size', 'calc(13.5px * var(--caption-scale)) !important'),
                    ('line-height', '1.5 !important'),
                    ('font-weight', '400 !important'),
                    ('letter-spacing', 'normal !important'),
                    ('text-transform', 'none !important')):
                if re.search(r'%s\s*:' % re.escape(prop), body):
                    body = re.sub(r'%s\s*:[^;]*;' % re.escape(prop),
                                  '%s: %s;' % (prop, literal), body, count=1)
                else:
                    body += '\n  %s: %s;' % (prop, literal)
        elif which == 'M2':
            body = re.sub(r'max\(\s*([0-9.]+)px\s*,\s*(var\([^()]*(?:\([^()]*\))?[^()]*)\)',
                          r'\2', body, count=1)
        elif which == 'M3':
            if re.search(r'color\s*:', body):
                body = re.sub(r'color\s*:[^;]*;', 'color: #e8eef2 !important;',
                              body, count=1)
            else:
                body += '\n  color: #e8eef2 !important;'
        return head + body + tail

    return pattern.sub(each, css)


def main(argv):
    neg = '--neg-arm' in argv[1:]
    unified = read(UNIFIED)
    themes = collect_themes()
    if not themes:
        print('VERDICT: CANNOT-MEASURE -- nenhum tema lido de %s' % (THEMES,))
        return 3

    if neg:
        # the control is the READER: mutate the sheet, not the code
        caught = 0
        total = 0
        tmp = tempfile.mkdtemp(prefix='theme-identity-')
        try:
            for which, owner in (('M1', 'A2'), ('M1', 'A3'),
                                 ('M2', 'A4'), ('M3', 'A5')):
                total += 1
                path = os.path.join(tmp, '%s.css' % which)
                with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write(mutate(unified, which))
                arms = judge(read(path), themes)
                red = [n for n, ok, _ in arms if not ok]
                ok = any(n.startswith(owner) for n in red)
                caught += 1 if ok else 0
                print('NEG-ARM %s -> %s (%s) red=%r' % (
                    which, 'CAUGHT' if ok else 'NOT-CAUGHT', owner, red))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print('\nVERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por desenho: o braco '
              'negativo devolve 1 quando APANHA)' % (
                  'PASS' if caught == total else 'FAIL', caught, total))
        return 1 if caught == total else 0

    arms = judge(unified, themes)
    bad = [n for n, ok, _ in arms if not ok]
    for name, ok, detail in arms:
        print('%-18s %s  %s' % (name, 'PASS' if ok else 'RED ', detail))
    print('\nVERDICT: %s  arms %d/%d%s' % (
        'PASS' if not bad else 'FAIL', len(arms) - len(bad), len(arms),
        '' if not bad else '  red=%r' % (bad,)))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
