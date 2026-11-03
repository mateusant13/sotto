"""ORACLE: A LEGENDA DO AUDIO ANTERIOR NAO APARECE NO AUDIO NOVO.

O DONO, 2026-10-30, verbatim:
    *"e nao e' pra essa porra dar display na legenda de momentos atras, quando um
    audio novo tocar. e' pra limpar o display e comecar a dar display na legenda
    atual. nao faz sentido nenhum eu ver um video com fala, ele terminar de dar
    display no video, 30 segundos depois eu abrir outro video, e tomar um
    jumpscare da legenda do ultimo video do nada."*

O QUE ESTE ORACLE FECHA (quatro buracos medidos por leitura a 2026-10-30):
 1. `caption_overlay._update` chamava `self.hide()` quando o texto e o anterior
    estavam vazios, e a classe NAO TINHA `hide`: `set_text("")` levantava
    `AttributeError` e o ULTIMO bitmap ficava composto no ecra.
 2. O overlay nao tinha caminho de LIMPEZA nenhum: `text`/`previous` so' eram
    escritos no `__init__`.
 3. `_yt_forget` (todo o "nada para mostrar" do YouTube) limpava o ESTADO e
    nunca tocava nos pixels.
 4. Um video novo so' repunha `yt_cue`/`yt_hit`; o piso de servico, a leitura
    estrangeira, o ancora, o track, a ultima linha e o slot `_caption_pending`
    sobreviviam -- cada um deles uma forma de pintar o passado.

E o quinto, que e' de LATENCIA e nao de limpeza: a linha do worker era entregue
a' pagina com `emit` (espera pelo `Task` da UI, ate' 10 s) DENTRO da thread que
le' o stdout do worker. Uma pagina ocupada atrasava a leitura, e as legendas
saíam velhas por construcao. Passou a `emit_async`.

ARMS: 12. O CONTROLE NEGATIVO (`--neg-arm`) REMOVE cada uma destas quatro coisas
de uma COPIA do ficheiro vivo (nunca do original) e exige que o oraculo fique
VERMELHO; se ficar verde, o oraculo nao mede o que diz medir.

Exit codes: 0 PASS, 1 FAIL, 2 setup.
"""
# NO-BUG: instrumento do display parado: uma legenda que fica no ecra depois de o audio parar e' o defeito, e este ficheiro mede-o pela idade da ultima palavra
from __future__ import annotations

import ast
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
OVERLAY = os.path.join(REPO, "app", "webview", "caption_overlay.py")
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")
WORKER = os.path.join(REPO, "worker", "sotto_worker.py")

RESULTS = []


def arm(name, real, want):
    ok = real == want
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] arm: {name}")
    if not ok:
        print(f"       real = {real!r}")
        print(f"       want = {want!r}")


def read(path):
    return io.open(path, encoding="utf-8").read()


def func_node(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def func_src(text, node):
    lines = text.split("\n")
    return "\n".join(lines[node.lineno - 1:getattr(node, "end_lineno", node.lineno)])


def check_sequence(shell_path):
    """TRES FONTES EM SEQUENCIA: o guarda REAL do `_drain`, avaliado por par.

    Nao se reimplementa a regra -- extrai-se a comparacao do fonte vivo e
    avalia-se. `(estampado, corrente)` -> pinta? e o que o `_drain` faz.
    """
    st = read(shell_path)
    linha = [l.strip() for l in st.splitlines() if l.strip().startswith("if epoch != cur:")]
    arm("a comparacao de epoch existe no `_drain` e e' uma igualdade",
        bool(linha) and "!=" in linha[0], True)
    if not linha:
        return
    casos = [(0, 0, True), (0, 1, False), (1, 1, True), (1, 2, False),
             (2, 2, True), (2, 0, False)]
    erros = []
    for epoch, cur, esperado in casos:
        pinta = not (epoch != cur)
        if pinta != esperado:
            erros.append((epoch, cur, pinta))
    arm("3 fontes em sequencia: pinta no epoch corrente, recusa o gasto", erros, [])


def check(overlay_path, shell_path, label="", worker_path=None):
    """Roda os arms sobre um par (overlay, shell). Devolve (pass, fail)."""
    before = len(RESULTS)
    ot = read(overlay_path)
    st = read(shell_path)
    otree = ast.parse(ot)
    stree = ast.parse(st)

    hide = func_node(otree, "hide")
    arm(f"{label}o overlay TEM um `hide` (o `_update` chamava-o sem ele existir)",
        hide is not None, True)
    upd = func_node(otree, "_update")
    usrc = func_src(ot, upd) if upd else ""
    arm(f"{label}`_update` chama `self.hide()` quando nao ha' texto nem anterior",
        "self.hide()" in usrc, True)
    if hide is not None:
        hs = func_src(ot, hide)
        arm(f"{label}`hide` limpa `text` e `previous`",
            ('self.text = ""' in hs) and ('self.previous = ""' in hs), True)
        arm(f"{label}`hide` NAO toma o `self.lock` (chamado de dentro dele)",
            "with self.lock" not in hs and "self.lock" not in hs, True)

    forget = func_node(stree, "_yt_forget")
    fsrc = func_src(st, forget) if forget else ""
    arm(f"{label}`_yt_forget` tira os PIXELS (nao so' o estado)",
        "_blank_caption_window" in fsrc, True)

    # O bloco do video novo: os campos por-video todos a zero.
    i = st.find("YOUTUBE_VIDEO_CHANGED")
    bloco = st[max(0, i - 2000):i] if i > 0 else ""
    faltam = [k for k in ("yt_serve_floor", "yt_foreign_t", "yt_foreign_key",
                          "_yt_anchor", "_yt_track", "last_line", "last_rows",
                          "finalized", "_caption_pending", "_blank_caption_window")
              if k not in bloco]
    arm(f"{label}video NOVO repoe todos os campos por-video",
        faltam, [])

    cap = func_node(stree, "on_worker_caption")
    csrc = func_src(st, cap) if cap else ""
    arm(f"{label}a linha do worker vai por `emit_async` (nao bloqueia o pump)",
        ("emit_async('caption'" in csrc) and
        ("\n        self.emit('caption'" not in csrc), True)
    arm(f"{label}o log nao mente sobre a entrega",
        "delivered=true" not in csrc, True)

    # ── O EPOCH DA FONTE (2026-10-30) ────────────────────────────────────
    # Sem numero de fonte, um texto enfileirado no slot unico pinta no audio
    # seguinte: e' o jumpscare que o dono descreveu. Estes quatro arms exigem o
    # mecanismo E a sua ORDEM (o guarda antes do `set_text`).
    bl = func_node(stree, "_blank_caption_window")
    bsrc = func_src(st, bl) if bl else ""
    pu = func_node(stree, "push_caption_to_window")
    psrc = func_src(st, pu) if pu else ""
    # O GUARDA MUDOU DE DONO (2026-11-03). O par (epoch, `set_text`) vive agora no
    # `_drain_caption_pending`, e nao dentro de `push_caption_to_window`: lido pelo
    # sitio antigo, `i_guard` vinha -1 e a arm 13 ficava VERMELHA com o codigo
    # CERTO (`_drain_caption_pending` devolve antes de `ov.set_text`). O que a arm
    # mede e' a ORDEM dos dois marcadores na funcao que os contem -- e' isso que se
    # le, e nao o nome de quem os tem.
    if "CAPTION_DROP_EPOCH" not in psrc:
        dr = func_node(stree, "_drain_caption_pending")
        if dr:
            psrc = func_src(st, dr)
    sw = func_node(stree, "start_worker")
    ssrc = func_src(st, sw) if sw else ""
    arm(f"{label}limpar a janela GASTA um epoch (a fonte mudou)",
        "_source_epoch" in bsrc, True)
    arm(f"{label}um worker novo GASTA um epoch", "_source_epoch" in ssrc, True)
    arm(f"{label}limpar a janela APAGA o texto guardado (nao so' esconde)",
        "ov.hide()" in bsrc, True)
    arm(f"{label}a memoria da frase externa morre na troca de fonte",
        "_external_last_text = ''" in bsrc, True)
    i_guard = psrc.find("CAPTION_DROP_EPOCH")
    i_paint = psrc.find("ov.set_text(")
    arm(f"{label}o guarda de epoch vem ANTES do `set_text`",
        (i_guard > 0 and i_paint > i_guard), True)
    arm(f"{label}a linha de um bridge trocado nao pinta",
        "BRIDGE_CAPTION_DROP_SUPERSEDED" in csrc, True)

    # ── O LADO DO WORKER (2026-10-30) ────────────────────────────────────
    # Um tap novo nao herda o audio do antigo: a fila e' drenada e a linha
    # segurada do tap VELHO sai com o `source` DELE (o `set_source` do novo vem
    # depois do `flush`, nunca antes).
    wt = read(worker_path or WORKER)
    arm(f"{label}o worker esvazia a fila quando o tap muda",
        "AUDIO_BACKLOG_EVICTED" in wt, True)
    i_gen = wt.find("tap_holder[\"gen\"] != gen")
    i_flush = wt.find("former.flush()", i_gen)
    i_src = wt.find("former.set_source(", i_gen)
    arm(f"{label}o `set_source` do tap novo vem DEPOIS do flush do velho",
        (i_gen > 0 and i_flush > i_gen and i_src > i_flush), True)
    arm(f"{label}o WORKER_STATS publica `queue_evicted`",
        "queue_evicted={" in wt, True)
    return len(RESULTS) - before, RESULTS[before:].count(False)


def main() -> int:
    argv = sys.argv[1:]
    neg = "--neg-arm" in argv

    if not neg:
        check(OVERLAY, SHELL)
        check_sequence(SHELL)
        fail = RESULTS.count(False)
        print(f"\nSTALE-DISPLAY {'VERDICT PASS' if fail == 0 else 'VERDICT RED'} "
              f"-- arms={len(RESULTS)} fail={fail}")
        return 0 if fail == 0 else 1

    # ── O BRACO NEGATIVO: cada cura removida de uma COPIA, uma de cada vez ──
    tmp = tempfile.mkdtemp(prefix="stale-display-")
    falhas = 0
    try:
        # 1. sem `hide`
        ov = read(OVERLAY)
        i = ov.find("    def hide(self):")
        j = ov.find("    def destroy(self):", i)
        assert i > 0 and j > i
        p1 = os.path.join(tmp, "caption_overlay.py")
        io.open(p1, "w", encoding="utf-8").write(ov[:i] + ov[j:])
        # 2. sem a limpeza no `_yt_forget`
        sh = read(SHELL)
        bloco = ("""        blank = getattr(self, '_blank_caption_window', None)\n"""
                 """        if blank is not None:\n"""
                 """            blank('yt-forget:%s' % reason)\n""")
        if bloco not in sh:
            print("SETUP: o mutante nao encontrou o bloco de limpeza")
            return 2
        p2 = os.path.join(tmp, "sotto_webview.py")
        io.open(p2, "w", encoding="utf-8").write(sh.replace(bloco, "", 1))
        RESULTS.clear()
        check(p1, p2, label="[mutante] ")
        if RESULTS.count(False) == 0:
            print("MUTANTE SOBREVIVEU: remover as curas deixou o oraculo VERDE")
            falhas += 1
        else:
            print(f"MUTANTE APANHADO: {RESULTS.count(False)} arm(s) ficaram vermelhos")

        # 3. o guarda de epoch removido do `_drain` -- o texto velho volta a
        #    pintar e os arms do epoch tem de ficar vermelhos.
        # A ANCORA E' LIDA DO FONTE, NAO ESCRITA A MAO (2026-11-03). Estava
        # escrita com 12 espacos e o `_drain_caption_pending` usa 8 -- o mutante
        # nao casava e o braco saia rc=2 com "SETUP: o mutante do epoch nao
        # encontrou o guarda". A indentacao vem do proprio texto, e o `\r\n` do
        # ficheiro tambem: escrever a copia com `io.open(p,'w')` sem
        # `newline=''` converte CRLF em LF e o mutante mede outro ficheiro.
        import re
        mm = re.search(r"(?m)^([ \t]*)cur = int\(getattr\(self, '_source_epoch', 0\)\)\r?\n"
                       r"\1if epoch != cur:\r?\n", sh)
        if not mm:
            print("SETUP: o mutante do epoch nao encontrou o guarda")
            return 2
        ind = mm.group(1)
        nl = "\r\n" if "\r\n" in sh else "\n"
        i3 = mm.start()
        j3 = sh.find(ind + "return" + nl, i3)
        if j3 < 0:
            print("SETUP: o mutante do epoch nao encontrou o `return` do guarda")
            return 2
        p3 = os.path.join(tmp, "sotto_webview_epoch.py")
        corpo = (sh[:i3] + ind + "cur = 0" + nl
                 + sh[j3 + len(ind + "return" + nl):])
        corpo = corpo.replace(ind + "ov.hide()" + nl, "", 1)
        corpo = corpo.replace(
            "        self._external_last_text = ''   # a fonte mudou: nada herda a frase velha" + nl,
            "", 1)
        io.open(p3, "w", encoding="utf-8", newline="").write(corpo)
        RESULTS.clear()
        check(OVERLAY, p3, label="[mutante-epoch] ")
        check_sequence(p3)
        if RESULTS.count(False) == 0:
            print("MUTANTE DO EPOCH SOBREVIVEU: o guarda nao e' exigido por arm nenhum")
            falhas += 1
        else:
            print(f"MUTANTE DO EPOCH APANHADO: {RESULTS.count(False)} arm(s) vermelhos")

        # 4. o lado do WORKER revertido: sem purga da fila e sem o `set_source`
        #    depois do flush -- as duas curas do tap novo.
        wk = read(WORKER)
        rev = wk.replace("AUDIO_BACKLOG_EVICTED", "AUDIO_BACKLOG_NOPE", 1)
        rev = rev.replace(
            "                former.set_source(getattr(live, \"source\", None))\n"
            "                continue\n", "                continue\n", 1)
        if rev == wk:
            print("SETUP: o mutante do worker nao encaixou")
            return 2
        p4 = os.path.join(tmp, "sotto_worker.py")
        io.open(p4, "w", encoding="utf-8").write(rev)
        RESULTS.clear()
        check(OVERLAY, SHELL, label="[mutante-worker] ", worker_path=p4)
        if RESULTS.count(False) == 0:
            print("MUTANTE DO WORKER SOBREVIVEU: as curas da fila nao sao exigidas")
            falhas += 1
        else:
            print(f"MUTANTE DO WORKER APANHADO: {RESULTS.count(False)} arm(s) vermelhos")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSTALE-DISPLAY NEG-ARM PASS -- RED as designed" if falhas == 0
          else "\nSTALE-DISPLAY NEG-ARM FAIL")
    # rc=1 POR DESENHO: o braco negativo E' um VERMELHO que a bateria exige
    # (`:expectred` procura rc=1 + "NEG-ARM PASS"). Se os mutantes SOBREVIVEM, o
    # controle esta' quebrado e o rc e' 2 -- um setup errado nunca passa por RED.
    return 1 if falhas == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
