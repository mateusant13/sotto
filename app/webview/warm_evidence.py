"""O motor quente PAGA-SE? A pergunta e' respondida pela serie, nao por omissao.

PORQUE EXISTE (D-04, medido 2026-11-12). O shell pede `SottoWarmEngine` a cada
abertura. O motor nasce ~1 s depois, carrega **7,5-26,0 s** de disco e ~1 GB
residente, e sai sozinho ao fim de `WARM_PARK_TTL_S = 600 s`
(`warm-engine.py`); as aberturas do dono distam **2 h a 16 h**. Resultado medido
no log inteiro do motor: **8** `WARM_LOAD_MS`, **8** `WARM_EXIT`, **ZERO**
`WARM_ATTACHED` -- cada carga foi jogada fora, e ela acontece exactamente no
arranque em que o shell ja' esta' a ler 1,9 GB.

A regra aqui e' a mais conservadora que resolve isso sem escolher o produto:
**com evidencia suficiente e zero anexos, nao se pede.** Uma evidencia curta
(menos de `MIN_LOADS` cargas) NAO autoriza recusar -- um historico de duas
aberturas nao diz nada sobre a terceira. E o instante em que um anexo acontecer
devolve o pedido sozinho, porque a serie e' relida a cada arranque.

O que este modulo NAO decide: se o TTL deve subir, nem se o anexo deve ser
adiado para depois da carga. Essas duas mudam o produto e sao do dono
(`docs/spec/10-DEFECTS.md`, D-04).
"""
import os

#: Quantas cargas de motor a serie precisa de mostrar antes de a recusa valer.
#: Tres e' o menor numero que distingue "ainda nao deu tempo" de "nunca paga":
#: com uma ou duas aberturas, uma sessao em que ele teria sido usado seria
#: suficiente para a regra estar errada.
MIN_LOADS = 3

#: Quanto do log do shell se le. O ficheiro de hoje tem 25 MB e roda; as
#: ocorrencias que interessam sao recentes por construcao (um anexo de hoje nao
#: esta' no comeco de um log de 25 MB).
SHELL_TAIL_BYTES = 512 * 1024

#: Linhas que contam como "o motor carregou" e "alguem o usou".
LOAD_TAG = "WARM_LOAD_MS"
ATTACH_TAG = "WARM_ATTACHED"


def verdict(loads, attaches):
    """A decisao, PURA: pedir o motor quente, e por que'.

    Devolve `{'request': bool, 'why': str, 'loads': int, 'attaches': int}`.
    """
    try:
        loads = max(0, int(loads))
    except (TypeError, ValueError):
        loads = 0
    try:
        attaches = max(0, int(attaches))
    except (TypeError, ValueError):
        attaches = 0
    out = {'request': True, 'why': 'pouca-evidencia',
           'loads': loads, 'attaches': attaches}
    if loads < MIN_LOADS:
        return out
    if attaches > 0:
        out['why'] = 'ja-anexou'
        return out
    out['request'] = False
    out['why'] = 'nunca-anexou'
    return out


def count_tag(path, tag, limit_bytes=None):
    """Quantas linhas de `path` levam `tag` como CAMPO. `None` = nao consegui ler.

    **A TAG NAO ABRE A LINHA**, e essa e' a razao de a contagem ser por campo:
    medido 2026-11-12 nos dois ficheiros que isto le:

        _main/warm-engine.log     `2026-11-11 20:47:16 WARM_LOAD_MS ms=7452.1 ...`
        _main/webview-run.log     `2026-11-08 18:57:23.068 sotto: WARM_FALLBACK_COLD ...`

    o primeiro poe um carimbo de tempo e o segundo um carimbo E o prefixo de
    processo, logo um `startswith(tag)` media ZERO cargas numa serie de oito --
    o defeito do instrumento que a arm A5 deste oraculo apanhou antes de a cura
    existir. Um campo que e' a tag, ou a tag seguida de `=` (o formato
    `TAG=campo`), conta; `WARM_LOAD_MS_DEFERRED` NAO conta, porque e' outra tag.

    `None` nunca vira zero: um log que nao se le nao e' um log sem a linha, e a
    diferenca entre os dois e' a diferenca entre "recusa" e "nao sei".
    """
    try:
        with open(path, 'rb') as fh:
            if limit_bytes:
                try:
                    fh.seek(0, os.SEEK_END)
                    size = fh.tell()
                    fh.seek(max(0, size - int(limit_bytes)))
                except OSError:
                    fh.seek(0)
            data = fh.read()
    except OSError:
        return None
    needle = tag.encode('utf-8')
    eq = needle + b'='
    total = 0
    for raw in data.splitlines():
        for field in raw.split():
            if field == needle or field.startswith(eq):
                total += 1
                break
    return total


def request_verdict_for(engine_log, shell_log):
    """A leitura dos dois logs + a decisao. Fail-open: sem serie, PEDE.

    Pedir demais custa 7,5-26,0 s de arranque; pedir de menos custa uma primeira
    legenda mais lenta numa sessao em que o motor teria servido. Quando a serie
    nao se le, o erro barato e' o de sempre -- pedir.
    """
    loads = count_tag(engine_log, LOAD_TAG)
    attaches = count_tag(shell_log, ATTACH_TAG, limit_bytes=SHELL_TAIL_BYTES)
    if loads is None or attaches is None:
        return {'request': True, 'why': 'sem-evidencia',
                'loads': loads, 'attaches': attaches}
    return verdict(loads, attaches)
