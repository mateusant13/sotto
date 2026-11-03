#!/usr/bin/env python
"""A REVELACAO PALAVRA-A-PALAVRA NO CAMINHO VIVO -- o que o PLAYER pinta, palavra a palavra.

O DONO, 2026-10-22, verbatim:
    *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou nao,
    igual o youtube."*

O QUE ESTE FICHEIRO JULGA, e o que NAO julga:

  * JULGA a JANELA que o caminho vivo produz no ramo `painted` (o ramo COMUM: o
    player esta a pintar a faixa que servimos) contra as LINHAS QUE O PLAYER
    PINTOU, lidas do proprio player e gravadas em
    `_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json`.
  * NAO julga os pixeis do ecra do dono: o overlay nativo (`caption_overlay.py`)
    desenha com GDI+, e o que o dono VE e ele. O que este ficheiro mede e o
    DADO que entra no overlay -- e a arm `overlay-receives-the-rows` diz se o
    texto que chega ao overlay ainda traz as quebras do player.

A ARMA QUE FALA DO DEFECTO (2026-10-29). MEDIDO no caminho vivo, antes da
correccao: o ramo `painted` montava a janela com o INICIO DO CUE
(`hit.cue.start + 0.001`), e `revealed_lines` corta a linha pelos relogios das
palavras -- logo SO A PRIMEIRA PALAVRA passava, e a linha nunca crescia:

    revealed_lines(cues, cue0.start + 0.001) -> ['Have']
    revealed_lines(cues, cue0.start + 1.000) -> ['Have you ever had to kill']

O `_main/youtube-1to1-oracle.py` NAO via este defeito: a arm `reveal-wired`
verifica que a CHAMADA existe, nao que o relogio que lhe passa seja o do
player. Este ficheiro existe para fechar essa lacuna, e por isso mede o
DESENHO (as linhas) e nao a existencia de uma chamada.

O CONTROLE NEGATIVO (`--neg-arm`): o paint e atrasado de proposito (uma palavra
a menos no que o player ja pintou, e o paint atrasado 300 ms). A arm
`reveal-matches-the-player` tem de ficar VERMELHA e o processo sai 1 POR DESENHO.

NAO LANCA NADA -- le ficheiros e corre python puro.

    python _main\\youtube-reveal-oracle.py
    python _main\\youtube-reveal-oracle.py --neg-arm
"""
# NO-BUG: check do objectivo do dono (a revelacao no CAMINHO VIVO, 2026-10-29): mede a
# janela revelada contra as linhas que o player pintou.
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))

FIXTURE = os.path.join(HERE, "fixtures", "yt-WdaHAGRBB6s.en-orig.json3")
LIVE = os.path.join(HERE, "fixtures",
                    "yt-WdaHAGRBB6s.break-position-20261026.json")
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")

#: As linhas que o player pintou, por instante, com o texto de cada linha.
#: Este artefacto foi gravado do PROPRIO player (`.ytp-caption-segment`), e e a
#: referencia contra a qual o desenho e julgado.


def load_cues():
    import youtube_captions
    with io.open(FIXTURE, encoding="utf-8") as fh:
        raw = fh.read()
    return youtube_captions.parse_json3(raw)


def load_live():
    with io.open(LIVE, encoding="utf-8") as fh:
        return json.load(fh)


def verbatim_live(src):
    """O caminho pintado devolve as LINHAS do player, e nao uma janela por relogio?

    MEDIDO 2026-11-03: este detector lia so' o corpo de `_youtube`, e o `_youtube`
    tinha sido partido em helpers com nome (`_yt_untracked_lines`,
    `_yt_painted_lines_match`, `_yt_aligned_painted`, `_yt_no_clock_lines`) --
    logo o corpo passou a ter UMA chamada `_yt_rows(painted,` e a arm dizia RED
    sobre um caminho que estava certo. Um detector preso a' FORMA da funcao
    envelhece com a funcao; este passa a ler a ARVORE, e conta a chamada em
    QUALQUER metodo do ficheiro (`_yt_rows` com o `painted` como 1.o argumento).

    `window_by_paint(` continua a ser proibido em TODO o ficheiro: e' a janela
    por relogio de palavra, o que fazia a linha construir-se ao longo do cue
    (imagens 1 e 2 do dono, 2026-11-02).
    """
    if not src:
        return False
    import ast
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    painted_calls = 0
    clock_window = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None) or ""
        if name == "_yt_rows":
            first = node.args[0] if node.args else None
            if getattr(first, "id", None) == "painted":
                painted_calls += 1
        elif name == "window_by_paint":
            clock_window += 1
    return painted_calls >= 2 and clock_window == 0


def old_clock_in_code(path):
    """O relogio ANTIGO (`cue.start + 0.001`) ainda esta no CODIGO?

    Le a ARVORE DE SINTAXE, nao o texto: a sintaxe do Python nao tem
    comentarios, logo o que esta aqui e CODIGO e nao a documentacao do
    defeito. (MEDIDO 2026-10-29: um `any(v in src)` acusava o comentario que
    explica o defeito -- um detector que castiga quem documenta a regra e um
    detector que nao serve.)

    Devolve a LISTA de achados (vazia = o defeito nao esta no codigo).
    """
    import ast

    try:
        with io.open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (OSError, SyntaxError) as exc:
        return ["<nao leu %s: %r>" % (path, exc)]

    achados = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
            continue
        # `X + 0.001` -- o deslocamento do relogio antigo.
        right = node.right
        if not (isinstance(right, ast.Constant) and isinstance(right.value, float)
                and abs(right.value - 0.001) < 1e-9):
            continue
        try:
            texto = ast.unparse(node.left)
        except (AttributeError, ValueError):
            texto = ""
        if "start" in texto:
            achados.append("linha %d: %s + 0.001" % (node.lineno, texto))
            continue
        # A forma INTERMEDIA: a variavel foi ATRIBUIDA a partir do inicio do
        # cue, e e a variavel que entra no `+ 0.001`.
        # MEDIDO 2026-10-29: `hit.get('cue', {}).get('start') or 0.0` e um
        # `BoolOp` (o `or`), nao uma cadeia de atributos -- por isso o
        # detector precisa de seguir a ATRIBUICAO da variavel, e nao apenas o
        # texto do lado esquerdo.
        if isinstance(node.left, ast.Name):
            for assign in ast.walk(tree):
                if not isinstance(assign, ast.Assign):
                    continue
                if not any(isinstance(t, ast.Name) and t.id == node.left.id
                           for t in assign.targets):
                    continue
                try:
                    valor = ast.unparse(assign.value)
                except (AttributeError, ValueError):
                    continue
                if "start" in valor:
                    achados.append("linha %d: %s (=%s) + 0.001"
                                   % (node.lineno, node.left.id, valor))
                    break
    return achados


def norm(text):
    """O texto como o ecra o mostra: espacos normalizados, marcador `>>` de fora.

    O `>>` e o marcador do PLAYER (o "speaker" das legendas automaticas) e o
    shell tira-o antes de pintar (`clean_external_text`), entao a comparacao
    tem de o tirar dos dois lados -- senao a arm mede o marcador, nao a legenda.
    """
    import re
    out = re.sub(r"^\s*(?:[>\u00bb\u203a]+\s*)+", "", str(text or ""))
    return " ".join(out.split())


def hit_from_player(rows, cues, live_indexes):
    """O `hit` do ALINHAMENTO DE PRODUCAO, a partir do que o player pintou.

    MEDIDO 2026-10-29: esta funcao ANTES reconstruia o `hit` a mao, e a
    reconstrucao era o que nao batia -- ela produzia um `hit` SEM
    `from_index`, e sem `from_index` a janela de producao (`window_by_paint`)
    nunca consegue reconstruir a LINHA QUE ROLA PARA FORA (a 3a linha que o
    player mostra). O resultado eram 2 divergencias em 10 amostras, e o
    instrumentos media uma coisa que a PRODUCAO nao faz.

    Agora chama a FUNCAO DE PRODUCAO (`youtube_captions.align_painted`), que e
    a que o ramo `painted` de `sotto_webview._youtube` chama. O artefacto
    gravado (as linhas que o player pintou) continua a ser a FONTE: o que se
    alinha e o que o player pintou, contra a faixa servida. O player nao esta a
    correr e nao e lido.

    O marcador `>>` de orador e MANTIDO nos dois lados: o payload tem
    (`'>> No.'`) e o player tambem o pinta (`'>> No.'`), e o alinhamento de
    producao casa as palavras tal como estao.
    """
    import youtube_captions
    painted = []
    for row in rows:
        painted.extend(str(row or "").split())
    if not painted:
        return None
    return youtube_captions.align_painted(cues, painted)


def live_cues(cues, t):
    """Os cues vivos em `t`, com os indices de cada um."""
    out = []
    for index, cue in enumerate(cues):
        start = float(cue.get("start") or 0.0)
        end = float(cue.get("end") or 0.0)
        if end > start and start <= t < end:
            out.append(index)
    return out


def window_of(cues, hit, indexes, capacity):
    """A janela que o CAMINHO VIVO produz -- a MESMA funcao de producao.

    MEDIDO 2026-10-29: esta funcao passava `sub = [cues[i] for i in indexes]`
    (SO os cues vivos) ao `window_by_paint`. Mas o `hit` do `align_painted` de
    PRODUCAO traz `index` e `from_index` como INDICES DA FAIXA COMPLETA, e o
    `window_by_paint` os usa como indices da lista que recebe. Passar um
    subconjunto desalinhavava os dois: o `from_index` apontava para a posicao
    errada da sub-lista e a linha que rola para fora (a 3a linha) nunca
    aparecia.

    A PRODUCAO passa a FAIXA INTEIRA (`track.get('cues')`), e e isso que esta
    MIRROR tem de fazer para medir a mesma coisa.

    A funcao chamada aqui e `youtube_reveal.window_by_paint`, que e a que o
    ramo `painted` de `sotto_webview._youtube` chama. Chamar a funcao de
    PRODUCAO (e nao uma reimplementacao) e o que torna esta arm uma MIRROR e
    nao um teste de uma copia.
    """
    import youtube_reveal
    return youtube_reveal.window_by_paint(cues, hit, capacity)


def old_window(cues, indexes, hit, capacity):
    """A JANELA ANTES DA CORRECCAO: o relogio do INICIO DO CUE.

    Serve para a arm `the-old-clock-was-broken`: o defeito tem de ser
    VISIVEL aqui, senao o conserto nao tem contra o que ser medido.

    MEDIDO 2026-10-29: usa a FAIXA INTEIRA, como a janela viva, para que as
    duas arms sejam comparaveis -- a unica diferenca entre elas e o relogio
    (o inicio do cue contra as palavras pintadas).
    """
    import youtube_window
    cue = (hit or {}).get("cue") or {}
    t = float(cue.get("start") or 0.0) + 0.001
    return youtube_window.revealed_lines(cues, t, capacity)


def shell_src():
    try:
        with io.open(SHELL, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def wiring_faltas(src):
    """As ancoras do caminho vivo que tem de existir.

    Nao e a MESMA coisa que `reveal-wired` do `youtube-1to1-oracle.py`: essa
    verifica que `revealed_lines` e chamada; esta verifica que o ramo
    `painted` usa a JANELA PELAS PALAVRAS PINTADAS e que o relogio do inicio do
    cue saiu daquele ramo.
    """
    checks = (
        ("o ramo painted usa a janela pelas palavras pintadas",
         "youtube_reveal.window_by_paint("),
        ("o ramo painted nao usa mais o inicio do cue como relogio",
         "hit.get('cue', {}).get('start') or 0.0) + 0.001"),
    )
    return [nome for nome, agulha in checks if agulha in (src or "")]


def medir(live, cues, capacity=3, delay_words=0):
    """Mede as tres coisas: a janela viva, a janela antiga, e a diferenca.

    MEDIDO 2026-10-29: as amostras que o ALINHAMENTO DE PRODUCAO nao consegue
    casar nao sao descartadas em silencio -- sao CONTADAS e reportadas. A
    amplitude (`_ALIGN_MIN_EXACT = 3` palavras casadas) e o que produz a
    amostra de t=0,023 s: com uma unica palavra pintada nao ha alinhamento
    possivel, e a PRODUCAO nessa altura tambem nao teria nada. Contar o
    denominador errado (medir so o que casou) seria medir uma fracao e
    chamar-lhe medida.
    """
    same = 0
    diffs = []
    old_same = 0
    total = 0
    no_hit = 0
    no_live = 0
    for sample in live.get("samples") or ():
        t = float(sample.get("t") or 0.0)
        rows = list(sample.get("youtube") or ())
        indexes = live_cues(cues, t)
        if not indexes:
            no_live += 1
            continue
        hit = hit_from_player(rows, cues, indexes)
        if hit is None:
            no_hit += 1
            continue
        total += 1
        if delay_words:
            hit = dict(hit)
            hit["aligned"] = max(0, int(hit.get("aligned") or 0) - delay_words)
        got = [norm(x) for x in window_of(cues, hit, indexes, capacity)]
        want = [norm(x) for x in rows]
        if got == want:
            same += 1
        else:
            diffs.append({"t": t, "youtube": want, "sotto": got})
        old = [norm(x) for x in old_window(cues, indexes, hit, capacity)]
        if old == want:
            old_same += 1
    return {"total": total, "same": same, "diffs": diffs, "old_same": old_same,
            "no_hit": no_hit, "no_live": no_live,
            "samples": len(live.get("samples") or ())}


def main(argv=None):
    ap = argparse.ArgumentParser(description="A revelacao palavra-a-palavra no caminho vivo.")
    ap.add_argument("--neg-arm", action="store_true",
                    help="atrasar a pintura de proposito: tem de dar RED")
    ap.add_argument("--capacity", type=int, default=3,
                    help="linhas da janela (o player pintou 3 em 4 de 16 amostras)")
    ap.add_argument("--write", default=None, help="escrever o relatorio")
    args = ap.parse_args(argv)

    if not os.path.exists(FIXTURE) or not os.path.exists(LIVE):
        print("REVEAL NO-VERDICT -- faltam o payload ou o artefacto do player")
        return 2

    cues = load_cues()
    live = load_live()
    src = shell_src()

    out = []
    add = out.append
    add("referencia     : %s (linhas pintadas pelo proprio player)" % os.path.basename(LIVE))
    add("payload        : %s" % os.path.basename(FIXTURE))
    add("janela         : %d linhas | cues com relogio: %d/%d"
        % (args.capacity,
           sum(1 for c in cues if c.get("words")), len(cues)))
    add("")

    delay = 1 if args.neg_arm else 0
    m = medir(live, cues, capacity=args.capacity, delay_words=delay)
    if args.neg_arm:
        add("BRACO NEGATIVO: a pintura atrasa %d palavra(s)" % delay)

    faltas = wiring_faltas(src)
    # O `wiring` procura o texto do RELOGIO ANTIGO para o ver AUSENTE; a lista
    # acima devolve os nomes cujo texto ESTA no ficheiro. Invertido aqui.
    #
    # MEDIDO 2026-10-29 (DUAS VEZES, e as duas pela mesma razao):
    #   1. a linha estava ESCRITA como um `any(...)` sobre um gerador VAZIO
    #      (`for _n, _a in ()`), que e um `any([])` -- sempre falso. A arm
    #      dizia "o relogio antigo NAO esta no ramo painted" sem nunca ter
    #      olhado para o ficheiro. Um gerador vazio e um verificador que nao ve.
    #   2. corrigido para um `any(v in src)`, passou a disparar sobre o
    #      COMENTARIO que explica o defeito ("`hit.cue.start + 0.001`"), e nao
    #      sobre codigo. Um detector que acusa a propria documentacao e um
    #      detector que castiga quem documenta a regra. O mesmo principio do
    #      `lane-screen-gate`: o detector le CODIGO, nao comentarios.
    #
    # Por isso o texto procurado e lido da ARVORE DE SINTAXE do Python, que
    # nao tem comentarios -- e o que separa "a regra esta escrita" de "a regra
    # esta no codigo".
    tem_velho = bool(old_clock_in_code(SHELL))
    # A LEI MUDOU A 2026-11-02 (ordem do dono: *"copiando 1:1 sem truncar
    # palavras"*). A janela por relogio de palavra era o DEFEITO -- a linha
    # construia-se ao longo do cue --, por isso o caminho vivo deixou de a
    # chamar e passou a devolver as LINHAS que o player desenha. O que se
    # verifica agora e essa chamada; a janela continua provada como ENGINE na
    # arma `reveal-matches-the-player`, que a chama directamente.
    add("caminho vivo    : as linhas pintadas do player sao a legenda: %s"
        % ("SIM" if verbatim_live(src) else "NAO"))
    add("                  o relogio do inicio do cue ainda esta no ramo painted: %s"
        % ("SIM (DEFEITO)" if tem_velho else "NAO"))
    add("")

    add("elemento                       veredicto  medicao")
    add("reveal-matches-the-player      %-10s linhas iguais: %d/%d"
        % ("GREEN" if m["same"] == m["total"] and m["total"] else "RED",
           m["same"], m["total"]))
    add("cobertura                       %-10s %d/%d amostras medidas (%d sem cues vivos, "
        "%d sem alinhamento de %d palavras)"
        % ("GREEN" if m["no_hit"] == 0 else "PARCIAL",
           m["total"], m["samples"], m["no_live"], m["no_hit"],
           3))
    add("the-old-clock-was-broken       %-10s a janela antiga tambem batia: %d/%d"
        % ("GREEN" if m["old_same"] < m["total"] else "RED",
           m["old_same"], m["total"]))
    add("wiring-is-live                 %-10s as linhas pintadas sao a legenda, "
        "sem janela por relogio"
        % ("GREEN" if verbatim_live(src) else "RED"))
    add("")

    if m["diffs"]:
        add("divergencias (as primeiras 6):")
        for d in m["diffs"][:6]:
            add("  t=%.3f youtube=%s" % (d["t"], d["youtube"]))
            add("         sotto  =%s" % (d["sotto"],))
        add("")

    bad = 0
    if not (m["same"] == m["total"] and m["total"]):
        bad = 1
    if m["old_same"] >= m["total"] and m["total"]:
        # O defeito antigo tem de ser visivel: se a janela antiga tambem batesse,
        # este ficheiro nao mediria nada.
        bad = 1
    if not verbatim_live(src):
        bad = 1
    if tem_velho:
        # O relogio antigo no ramo `painted` e o DEFECTO que este ficheiro
        # existe para apanhar. Se ele voltar, o veredicto tem de ser VERMELHO
        # -- e nao uma nota na margem.
        bad = 1

    text = "\n".join(out)
    print(text)
    if args.write:
        with io.open(args.write, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")

    if args.neg_arm:
        # O braco negativo tem de ser VERMELHO: se a arm principal continuasse
        # verde com a pintura atrasada, o instrumento nao mede nada.
        if bad:
            print("NEG-ARM PASS (a janela ja nao batia com o atraso)")
            return 1
        print("NEG-ARM FAIL -- a janela continuou a bater com a pintura atrasada")
        return 1
    return bad


if __name__ == "__main__":
    sys.exit(main())
