"""A arvore e os segmentos de um texto, UMA vez por CONTEUDO.

POR QUE ESTE MODULO EXISTE (medido 2026-11-12). Duas operacoes desta casa custam
com o TAMANHO da fonte, nao com o trabalho da arm:

* `ast.parse` e' um `compile` da fonte inteira. Num `--neg-arm` que corre cinco
  copias mutadas do mesmo ficheiro, o mesmo texto era re-parseado por arm -- e
  `ast.parse` sobre o shell de 26 774 linhas custa ~0,26 s.
* `ast.get_source_segment` re-parte a fonte INTEIRA em cada chamada (no CPython,
  `_splitlines_no_ff` + `''.join`). Medido: **262 chamadas = 58,0 s** no
  `audio-back-detector`, **37,6 s em 51 chamadas** no `window-drag`, **27,8 s** no
  `altc-gesture`, **24,9 s de `compile`** no `gaming-hotkey`.

A CHAVE E' O CONTEUDO, NUNCA O CAMINHO. As copias mutadas tem o mesmo nome de
ficheiro e texto diferente; o caminho real e a copia nao mutada do mesmo texto
partilham a entrada -- que e' exactamente a propriedade que a medicao mostrou ser
paga dezenas de vezes.

O modulo nasceu de cinco copias privadas da mesma cura em QUATRO oraculos
(`altc-gesture`, `window-drag`, `gaming-hotkey`, `audio-back-detector`), mais a
sexta em `live-ack` (que ja' passava o nome do ficheiro ao `ast.parse`) e a de
`youtube-cdp-source`. Uma convencao por problema: quem precisar disto importa
daqui, nao reescreve.
"""
from __future__ import annotations

import ast
import hashlib

_TREES: dict = {}
_LINES: dict = {}


def _key(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8", "replace")).hexdigest()


def tree(source: str, where: str = "<unknown>"):
    """A `ast.Module` do texto, parseada no maximo uma vez por conteudo.

    `where` e' o nome que aparece num traceback de erro de sintaxe; nao entra na
    chave, porque o mesmo texto tem de partilhar a entrada entre o ficheiro real e
    a copia mutada (e' essa a propriedade que a medicao mostrou ser paga dezenas
    de vezes).
    """
    key = _key(source)
    hit = _TREES.get(key)
    if hit is None:
        hit = ast.parse(source, filename=where)
        _TREES[key] = hit
    return hit


def lines(source: str):
    """As linhas na particao que o CPython usa (sem dividir no `\\f`).

    `ast._splitlines_no_ff` e' privada; usamo-la quando existe para a particao ser
    a MESMA que `get_source_segment` faria (uma particao diferente desloca o
    segmento e a arm julgaria o texto do lado), e so' caímos no
    `splitlines(keepends=True)` se ela faltar.
    """
    key = _key(source)
    hit = _LINES.get(key)
    if hit is not None:
        return hit
    split = getattr(ast, "_splitlines_no_ff", None)
    out = split(source) if split else source.splitlines(keepends=True)
    _LINES[key] = out
    return out


def segment(source: str, node, missing=None):
    """`ast.get_source_segment(source, node)`, com as linhas ja' partidas.

    `missing` e' o que se devolve para um no' sem posicao final -- o chamador
    escolhe `""` (o oraculo que concatena) ou `None` (o que distingue ausencia).
    """
    if node is None:
        return missing
    if getattr(node, "end_lineno", None) is None \
            or getattr(node, "end_col_offset", None) is None:
        return missing
    rows = lines(source)
    first, last = node.lineno - 1, node.end_lineno - 1
    if last == first:
        return rows[first].encode()[node.col_offset:node.end_col_offset].decode()
    head = rows[first].encode()[node.col_offset:].decode()
    tail = rows[last].encode()[:node.end_col_offset].decode()
    return head + "".join(rows[first + 1:last]) + tail


def reset() -> None:
    """Esvazia as caches -- so' um teste que MUTA o mesmo texto em sitio o quer."""
    _TREES.clear()
    _LINES.clear()
