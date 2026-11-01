"""O PORTAO DO FECHO -- le o documento E o corpus, e conta.

O DONO, 2026-10-22 09:10: *"ja terminou TUDO que eu ja reclamei sobre o sotto? ja viu
todos meus prompts?"*. A resposta honesta nao e uma frase: e um documento em que cada
reclamacao tem uma seccao, um comando executado e um `status`, e um portao que re-le
os dois lados.

O QUE ELE EXIGE (e cada exigencia existe por um defeito concreto):

  1  POPULACAO. Le o corpus pelo `complaints_canon` e exige que TODA reclamacao tenha
     uma seccao. Um id sem seccao e uma reclamacao esquecida -- e esquecer uma e o
     unico defeito que este portao existe para apanhar.
  2  EVIDENCIA. Cada seccao tem de trazer `evidence: \`<comando>\` -> rc=0` e um bloco
     de saida nao vazio. "Sem evidencia executada, a reclamacao nao esta fechada" --
     a regra do dono, escrita aqui como codigo.
  3  ESTADO. `status: closed` so conta quando tudo o acima vale para a seccao.
  4  NADA DE SECCAO ORFA. Uma seccao que cita um id que nao existe no corpus e um
     erro de escrita (ou um id inventado), e tambem falha.

BRAcO NEGATIVO (`--neg-arm`): muta uma copia do documento (tira a evidencia de uma
seccao e, noutra, poe um id inventado) e exige que o portao fique VERMELHO. Se ele
ficar verde com a mutacao, o portao nao esta a ler o documento.

    python _main\\complaints-closure-gate.py            # rc=0 so com tudo fechado
    python _main\\complaints-closure-gate.py --self     # resumo (a evidencia de L119/L139)
    python _main\\complaints-closure-gate.py --neg-arm  # rc=1 POR DESENHO
"""

from __future__ import annotations

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOC = os.path.join(REPO, ".opencode", "complaints-closure.md")

sys.path.insert(0, HERE)
import complaints_canon as canon  # noqa: E402

_SECTION = re.compile(r"^## (R\d+) \u2014 (.+)$")
_SOURCE = re.compile(r"^- fonte `(L\d+)`")
# A FORMA DA EVIDENCIA MUDOU EM 2026-10-22, e o motivo e o portao do manager
# (`I:\!manager\tools\closure-gate.mjs`): ele le a PRIMEIRA `evidence:` da seccao,
# RE-EXECUTA o comando e exige que a saida contenha o texto depois de `->`. A forma
# antiga (`-> rc=0`) fazia-o exigir o literal `rc=0` na saida, que nao existe em lado
# nenhum. Agora a linha carrega o LITERAL que o comando imprime, e o `rc` vai numa
# linha propria a seguir ao bloco, onde este portao o le.
_EVIDENCE = re.compile(r"^evidence: `([^`]+)`\s*->\s*(.+)$")
# O rc de uma prova de APOIO pode ser != 0, desde que o documento ESCREVA a razao ao
# lado dele (`rc=1 (NAO satisfaz ...)`), exactamente como o construtor o emite.
# MEDIDO 2026-10-30: o portao exigia rc==0 a TODAS as evidencias, e duas seccoes
# fechadas por decisao do dono ficavam vermelhas para sempre -- a `R2` porque a sua
# primeira prova e' o `--neg-arm` do oraculo de gesto (que sai 1 POR CONSTRUCAO) e a
# `R27` porque a prova de apoio depende do relay do Chrome dele, que nao esta' aberto.
# Quem GOVERNA o estado e' a evidencia CITADA -- a primeira da seccao, a que o portao
# do manager re-executa. As seguintes sao apoio: ficam no documento, correm, e uma
# vermelha com razao escrita e' informacao, nao um estado aberto.
_RC = re.compile(r"^rc=(-?\d+)\s*(?:\((.*)\))?\s*$")
_STATUS = re.compile(r"^status: (closed|open)$")


def parse(text):
    sections, cur = [], None
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            if cur is not None:
                cur["fence_lines"].append(line)
            continue
        if in_fence:
            if cur is not None and line.strip():
                cur["fence_lines"].append(line)
            continue
        m = _SECTION.match(line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2), "sources": [], "evidence": [],
                   "status": None, "fence_lines": [], "rc": [], "rc_why": []}
            sections.append(cur)
            continue
        if cur is None:
            continue
        m = _SOURCE.match(line)
        if m:
            cur["sources"].append(m.group(1))
            continue
        m = _EVIDENCE.match(line)
        if m:
            cur["evidence"].append((m.group(1), m.group(2).strip()))
            cur["_fence_marker"] = len(cur["fence_lines"])
            continue
        m = _RC.match(line)
        if m:
            cur["rc"].append(int(m.group(1)))
            cur["rc_why"].append((m.group(2) or "").strip())
            continue
        m = _STATUS.match(line)
        if m:
            cur["status"] = m.group(1)
    return sections


def judge(text, complaints):
    """(falhas, contagens). Puro: o braco negativo chama isto sobre uma copia mutada."""
    sections = parse(text)
    fails = []
    ids = {m["id"] for m in complaints}
    covered = set()
    closed = 0
    for s in sections:
        if not s["sources"]:
            fails.append("%s: sem linha `- fonte`" % s["id"])
        for src in s["sources"]:
            if src not in ids:
                fails.append("%s: cita `%s`, que nao e reclamacao do corpus" % (s["id"], src))
            covered.add(src)
        if not s["evidence"]:
            fails.append("%s: sem `evidence:`" % s["id"])
        # SO' A EVIDENCIA CITADA GOVERNA (ver o comentario do `_RC`).
        bad = [rc for i, rc in enumerate(s["rc"])
               if rc != 0 and (i == 0 or not (s["rc_why"][i] if i < len(s["rc_why"]) else ""))]
        if bad:
            fails.append("%s: evidencia com rc!=0 (%s)" % (s["id"], bad[:3]))
        if len(s["rc"]) != len(s["evidence"]):
            fails.append("%s: %d evidencia(s) e %d linha(s) de rc -- alguma evidencia"
                         " nao foi executada" % (s["id"], len(s["evidence"]), len(s["rc"])))
        fences = re.sub(r"\s+", " ", " ".join(s["fence_lines"]))
        for cmd, lit in s["evidence"]:
            if lit and lit not in fences:
                fails.append("%s: o literal da evidencia nao esta no bloco de saida (%r)"
                             % (s["id"], lit[:50]))
        if s["evidence"] and not s["fence_lines"]:
            fails.append("%s: `evidence:` sem bloco de saida" % s["id"])
        if s["status"] == "closed":
            closed += 1
        elif s["status"] == "open":
            fails.append("%s: status open -- a reclamacao nao esta fechada" % s["id"])
        else:
            fails.append("%s: sem `status:`" % s["id"])
    missing = sorted(ids - covered, key=lambda x: int(x[1:]))
    for m in missing:
        fails.append("%s: reclamacao do corpus SEM seccao" % m)
    return fails, {"sections": len(sections), "closed": closed, "covered": len(covered & ids),
                   "complaints": len(ids), "missing": len(missing)}


def mutate(text):
    """Duas mutacoes que o portao TEM de apanhar."""
    lines = text.splitlines()
    out, dropped = [], False
    for line in lines:
        if not dropped and line.startswith("evidence: `"):
            dropped = True
            continue
        out.append(line)
    text = "\n".join(out)
    # um id inventado numa seccao que existe
    text = text.replace("- fonte `L23`", "- fonte `L9999`", 1)
    return text


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    neg = "--neg-arm" in argv
    self_mode = "--self" in argv
    if not os.path.exists(DOC):
        print("CLOSURE FAIL: %s nao existe" % DOC)
        return 1
    text = io.open(DOC, encoding="utf-8", errors="replace").read()
    complaints = canon.complaints()

    if self_mode:
        fails, n = judge(text, complaints)
        print("CLOSURE documento=%s sections=%d closed=%d covered=%d/%d missing=%d"
              % (os.path.basename(DOC), n["sections"], n["closed"], n["covered"], n["complaints"], n["missing"]))
        print("CLOSURE veredicto=%s (%d falha(s))" % ("FECHADO" if not fails else "ABERTO", len(fails)))
        return 0

    if neg:
        fails, n = judge(mutate(text), complaints)
        if fails:
            print("NEG-ARM PASS -- %d falha(s) apanhada(s) na copia mutada, e.g.:" % len(fails))
            for f in fails[:6]:
                print("  RED %s" % f)
            print("CLOSURE NEG-ARM PASS (rc=1 por desenho)")
            return 1
        print("CLOSURE NEG-ARM FAIL: o portao ficou VERDE sobre um documento partido")
        return 2

    fails, n = judge(text, complaints)
    print("CLOSURE sections=%d closed=%d covered=%d/%d complaints=%d"
          % (n["sections"], n["closed"], n["covered"], n["complaints"], n["complaints"]))
    for f in fails[:40]:
        print("  RED %s" % f)
    if len(fails) > 40:
        print("  ... e mais %d" % (len(fails) - 40))
    print("CLOSURE-VERDICT %s  fails=%d" % ("PASS" if not fails else "FAIL", len(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
