"""QUANDO O SILENCIO PROVA A CAUDA DA LINHA -- a decisao, num ficheiro so'.

PORQUE UM FICHEIRO PROPRIO (2026-11-04). A mesma razao que criou
`worker/engine_policy.py` e `app/panel/stable-words.js`: `worker/sotto_worker.py`
e `app/webview/sotto_webview.py` estao debaixo do ratchet de bytes/linhas do
`_main/code-health-oracle.py`, que recusa QUALQUER crescimento deles. Uma regra
nova que vive num ficheiro novo nao paga esse preco, e o worker fica com a
chamada (quatro linhas) em vez da regra.

O DEFEITO QUE ISTO CORRIGE, MEDIDO no log vivo do dono (2026-11-04, ultima
sessao, 191 pinturas que MUDARAM o texto no ecra):

    p50 = 195 ms   p90 = 1645 ms   <=400 ms = 54,5%

A distribuicao e' bimodal e nao ha praticamente nada entre 400 e 1500 ms. Os
400 ms sao a latencia real do caminho; os 1500 ms sao o relogio
`COMMIT_MAX_HOLD_MS` do PAINEL a soltar a cauda. A razao e' estrutural: o
`LineFormer` so' ve' o fim de uma frase quando o FRAGMENTO SEGUINTE chega
(`push`, condicao 1), e o bloco de audio que vem depois das ultimas palavras
decodifica VAZIO -- logo `push` nunca corre, e a ultima palavra (que a regra
`proven_text` segura por nao estar provada) espera pelo painel.

O SILENCIO E' A PROVA. Se ninguem esta' a falar, a palavra que o modelo emitiu
e' a palavra inteira. 0,8 s e' 1,5 blocos de 560 ms: um bloco quieto sozinho
nao publica nada, dois seguidos publicam.

O QUE ISTO NAO FAZ: nao FECHA a linha. `SENTENCE_GAP_S = 8.0` e' quem decide
onde a linha quebra, e baixar isso multiplicaria as linhas do historico -- uma
mudanca diferente da que a medicao pede. Isto publica o texto ACTUAL da linha
com `stable: true`, que e' exactamente o que o painel le' em
`app/panel/stable-words.js::wordsAreWhole` para nao segurar a palavra duas
vezes.
"""

#: Audio seconds of silence that PROVE the line's last word.
SILENCE_PROVE_S = 0.8


def decide(now_end, line_end, text, worthy, shown, last_proved):
    """Publish the line because the audio went quiet? `(text|None, guard)`.

    `now_end`  -- audio END of the newest block, whether or not it had words.
    `line_end` -- audio END of the last block that DID have words (`LineFormer._end`).
    `text`     -- the line's current full text (already tidied by the caller).
    `worthy`   -- the caller's own "this is worth showing" rule (`_worthy`).
    `shown`    -- what the owner is already looking at (`_shown`).
    `last_proved` -- the guard from the previous call; the caller stores the
                  second element back, so ONE silence publishes ONCE.

    Returns `(None, guard)` when nothing must be published -- the guard is still
    returned updated, because the silence HAS been proven and a later block of
    the same silence must not try again.
    """
    if not text or line_end is None or now_end is None:
        return None, last_proved
    try:
        gap = float(now_end) - float(line_end)
    except (TypeError, ValueError):
        return None, last_proved
    if gap < SILENCE_PROVE_S:
        return None, last_proved
    if last_proved is not None:
        try:
            if float(now_end) <= float(last_proved):
                return None, last_proved
        except (TypeError, ValueError):
            pass
    if not worthy or text == shown:
        return None, float(now_end)
    return text, float(now_end)
