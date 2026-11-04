"""ORACLE for the INCOMPLETE-WORD rule -- a palavra que ainda nao esta provada
nao vai para o ecra.

O DONO, 2026-10-30, verbatim:
    *"faz sotto identificar palavras que ainda nao estao completas e nao dar
    display. nunca vai dar display por exemplo em 'so' sem esperar virar 'sou'.
    em qualquer lingua"*

O QUE ESTE ORACLE FECHA
----------------------
`LineFormer` publica um PARCIAL de cada vez que a linha cresce. A ultima
palavra desse parcial nunca esta provada: o modelo pode ter cortado a palavra
a meio (`próx` | `ima`), e o dono le "próx" quando a palavra completa e
"próximo". A correcao chega um instante depois, o que faz a legenda tremer e
-- pior -- ENSINA o dono a ler palavras erradas.

A REGRA. Uma palavra so e MOSTRADA quando a proxima evidencia prova que
acabou: o fragmento seguinte NAO continua a palavra (o veredicto do tokenizer,
`chunk_is_continuation`), ou a linha fechou.

O QUE ESTE ORACLE NAO FAZ
-------------------------
Nao decide a LINGUA. A regra usa o marcador `▁` do SentencePiece, que e o
mesmo em qualquer lingua, entao a regra e a mesma para o portugues, o ingles e
o russo. Os arms abaixo usam palavras de varias linguas PARA PROVAR QUE A
REGRA NAO DEPENDE DA PALAVRA -- e nao para listar os dicionarios.

O CONTROLE NEGATIVO. Cada arm que a correccao ganha tem de dar VERMELHO contra
a implementacao de ANTES (`_ShowAll`), que publica a linha inteira. Um arm
verde que o controle tambem passa nao prova nada.

ARMS
----
 1  a palavra final de um parcial NAO e mostrada
 2  a palavra final volta assim que o fragmento seguinte prova que ela acabou
 3  um fragmento que CONTINUA a palavra mantem a palavra fora (o caso "so"/
    "sou": o token continua a palavra, logo ela nao pode ser mostrada)
 4  a palavra final que TERMINA em pontuacao E mostrada (nenhum token de
    continuacao pode vir depois de um ponto)
 5  uma linha so com a palavra suspeita nao publica NADA (o "nao dar display")
 6  a linha FECHADA sai com a palavra toda -- o historico tem a frase completa
 7  a regra e INDEPENDENTE DA LINGUA: as mesmas formas em varias linguas
 8  o texto estavel e um PREFIXO do texto completo (nada se perde)
 9  o texto estavel NUNCA cresce: e monotonico nao decrescente
10  uma palavra que ja estava provada nao volta a desaparecer

Exit codes: 0 PASS, 1 FAIL, 2 setup error. Nenhuma janela: python puro.
"""
# NO-BUG: instrumento da ordem do dono de 2026-10-30 (*"nunca vai dar display por
# exemplo em 'so' sem esperar virar 'sou'. em qualquer lingua"*). Mede a regra no
# worker vivo (15 bracos) e o braco negativo DESLIGA-a no ficheiro e exige RED.

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)
import sotto_worker as W  # noqa: E402

RESULTS = []


def arm(name, real, control, want, control_must_differ=True):
    ok = real == want
    differs = real != control
    good = ok and (differs or not control_must_differ)
    RESULTS.append(good)
    tag = "PASS" if good else "FAIL"
    print(f"[{tag}] arm: {name}")
    print(f"       real    = {real!r}")
    print(f"       want    = {want!r}")
    if control_must_differ:
        print(f"       control = {control!r}  (must differ: {'yes' if differs else 'NO'})")


def captions(events):
    return [e["text"] for e in events]


def drive(chunks, **kw):
    """`chunks` sao `(text, start, end, continues)`. Com `flush=True` (o
    padrao) a linha fecha no fim -- e a linha FECHADA tem a palavra toda,
    porque o fim do audio e a prova definitiva.

    Para medir a REGRA DO PARCIAL, use `flush=False`: so os parciais contam.
    """
    do_flush = kw.pop("flush", True)
    f = W.LineFormer(**kw)
    out = []
    for text, s, e, cont in chunks:
        out += f.push(text, s, e, continues=cont)
    if do_flush:
        out += f.flush()
    return out


def partials(chunks, **kw):
    """So os PARCIAIS: a linha nunca fecha, logo a ultima palavra fica
    suspensa. E o canal que o dono ve a crescer."""
    kw["flush"] = False
    return drive(chunks, **kw)


class _ShowAll:
    """A IMPLEMENTACAO DE ANTES: publica a linha INTEIRA, palavra final
    incluida. Este e o controle; tem de dar VERMELHO nos arms que a correccao
    ganha."""

    def __init__(self, min_chars=1, emit_partial=True, **_):
        self.min_chars = max(1, int(min_chars))
        self.emit_partial = bool(emit_partial)
        self._words = []
        self._shown = None
        self._closed = []

    def push(self, text, start=None, end=None, continues=False):
        frag = (text or "").strip()
        if not frag:
            return []
        cont = bool(continues) and bool(self._words)
        self._words.append((frag, cont))
        line = W.join_fragments(self._words)
        if not self.emit_partial or len(line.strip()) < self.min_chars:
            return []
        self._shown = line
        return [{"type": "caption", "text": line, "start": start, "end": end}]

    def flush(self):
        line = W.join_fragments(self._words)
        out = []
        if line and len(line.strip()) >= self.min_chars:
            self._closed.append({"type": "caption", "text": line,
                                 "start": None, "end": None,
                                 "final": True, "closed": True})
            if line != self._shown:
                out.append({"type": "caption", "text": line,
                            "start": None, "end": None})
        self._words = []
        return out

    def take_closed(self):
        out = self._closed
        self._closed = []
        return out


def drive_control(chunks, **kw):
    """O CONTROLE: a implementacao de ANTES, que mostra a linha INTEIRA."""
    do_flush = kw.pop("flush", True)
    f = _ShowAll(**kw)
    out = []
    for text, s, e, cont in chunks:
        out += f.push(text, s, e, continues=cont)
    if do_flush:
        out += f.flush()
    return out


def neg_arm():
    """O BRACO NEGATIVO: a regra desligada tem de dar VERMELHO.

    O que e desligado: `worker/stable_words.py::stable_text` passa a devolver
    o texto INTEIRO -- que e exactamente o comportamento de ANTES (a linha
    inteira no parcial). A regra e o unico que muda; o resto do oratorio
    corre igual.

    O QUE ESTE ARM PROVA: que os arms do oratorio NAO sao tautologias. Se
    algum arm passasse com a regra desligada, ele mediria alguma coisa que a
    regra nao controla -- e o oratorio nao diria nada sobre a ordem do dono.

    A mutacao e feita NO FICHEIRO VIVO (`worker/stable_words.py`), com uma
    copia de seguranca, e o ficheiro e restaurado no fim -- mesmo que o
    oratorio corra com `--neg-arm` a meio de outra coisa.
    """
    import shutil
    import tempfile

    alvo = os.path.join(WORKER, "stable_words.py")
    if not os.path.exists(alvo):
        print("NEG-ARM FAIL: worker/stable_words.py nao existe -- a regra "
              "nao esta onde este oratorio a procura.")
        return 2
    bak = tempfile.mkdtemp(prefix="incomplete-neg-") + os.sep + "stable_words.py.bak"
    shutil.copy2(alvo, bak)
    try:
        with open(alvo, encoding="utf-8") as fh:
            src = fh.read()
        # A MUTACAO: `open_word_start` diz que TUDO esta provado (a regra OFF).
        # O ALVO MUDOU a 2026-10-30: a regra deixou de viver em `stable_text`
        # (que so' corta por espaco e agora e' compatibilidade) e passou a viver
        # em `open_word_start`, que le a marca `▁` do tokenizer. Mutar a funcao
        # antiga deixava os arms VERDES com a regra a funcionar -- medido, e o
        # braco negativo recusou com "a mutacao nao encaixou" em vez de mentir.
        mutado = src.replace(
            "    if not text:\n        return 0, \"\"\n",
            "    return len(text), text\n", 1)
        if mutado == src:
            print("NEG-ARM FAIL: a mutacao nao encaixou -- o ficheiro "
                  "mudarou de forma e o braco negativo deixou de medir.")
            return 2
        with open(alvo, "w", encoding="utf-8") as fh:
            fh.write(mutado)
        # Recarrega o worker com o modulo mutado.
        for _mod in [m for m in list(sys.modules)
                     if m in ("stable_words", "sotto_worker")]:
            del sys.modules[_mod]
        import sotto_worker as W2
        sys.modules["sotto_worker"] = W2
        W_mut = W2
        f = W_mut.LineFormer(emit_partial=True)
        parciais = []
        for text, s, e, cont in [("eu vou", 0.0, 0.5, False)]:
            parciais += f.push(text, s, e, continues=cont)
        mostrado = [ev["text"] for ev in parciais]
        esperado = ["eu"]           # a regra ON segura "vou"
        if mostrado == esperado:
            print("NEG-ARM FAIL: com a regra DESLIGADA o oratorio ainda "
                  "passou (%r) -- os arms nao medem a regra." % (mostrado,))
            return 1
        print("NEG-ARM PASS: com a regra DESLIGADA o parcial mostra %r "
              "(a regra ON mostra %r) -- o portao tem dentes."
              % (mostrado, esperado))
        return 1  # rc=1 POR DESENHO: o braco negativo e um VERMELHO
    finally:
        shutil.copy2(bak, alvo)
        shutil.rmtree(os.path.dirname(bak), ignore_errors=True)
        for _mod in [m for m in list(sys.modules)
                     if m in ("stable_words", "sotto_worker")]:
            del sys.modules[_mod]


def main():
    """O oratorio. `--neg-arm` NEUTRALIZA a regra e tem de dar VERMELHO.

    O `--neg-arm` e o que a bateria usa para provar que o portao tem DENTES:
    se o portao passasse com a regra desligada, ele nao provaria nada. O
    mecanismo: o `stable_text` real e trocado por uma versao que devolve o
    texto INTEIRO (a implementacao de ANTES), e o oratorio tem de reportar
    FAIL -- e sair com codigo 1.
    """
    if "--neg-arm" in sys.argv:
        return neg_arm()

    # ── arm 1: a palavra final de um parcial NAO e mostrada ─────────────────
    # O fragmento "eu vou" tem duas palavras; a ultima ("vou") nao esta provada.
    # So os PARCIAIS contam aqui: a linha nunca fecha, logo a palavra fica
    # suspensa ate que a prova chegue.
    chunks = [("eu vou", 0.0, 0.5, False)]
    arm("a palavra final de um parcial nao e mostrada",
        captions(partials(chunks, emit_partial=True)),
        captions(drive_control(chunks, emit_partial=True)),
        ["eu"])

    # ── arm 2: a palavra volta quando o fragmento seguinte a prova ─────────
    # O segundo fragmento NAO continua a palavra, logo "vou" acabou: o partial
    # seguinte mostra "eu vou" inteiro.
    chunks = [("eu vou", 0.0, 0.5, False), ("cantar", 0.5, 1.0, False)]
    arm("a palavra provada pelo fragmento seguinte volta no partial seguinte",
        captions(partials(chunks, emit_partial=True)),
        captions(drive_control(chunks, emit_partial=True)),
        ["eu", "eu vou"])

    # ── arm 3: um fragmento que CONTINUA a palavra mantem a palavra fora ─────
    # O caso "so"/"sou": o token `so` nao tem marcador `▁`, logo o proximo
    # fragmento CONTINUA a palavra -- e ela nao pode ser mostrada. O texto
    # estavel e o que ja estava provado ANTES da palavra suspecta.
    chunks = [("ele so", 0.0, 0.5, False), ("u", 0.5, 1.0, True)]
    arm("um fragmento que continua a palavra mantem a palavra fora",
        captions(partials(chunks, emit_partial=True)),
        captions(drive_control(chunks, emit_partial=True)),
        ["ele"])

    # ── arm 4: uma palavra que TERMINA em pontuacao E mostrada ─────────────
    # Nenhum token de continuacao pode vir depois de um ponto: a palavra esta
    # provada pelo proprio texto.
    chunks = [("sim.", 0.0, 0.5, False)]
    arm("a palavra final que termina em pontuacao e mostrada",
        captions(partials(chunks, emit_partial=True)),
        captions(drive_control(chunks, emit_partial=True)),
        ["sim."],
        control_must_differ=False)

    # ── arm 5: uma linha so com a palavra suspeita nao publica NADA ─────────
    chunks = [("so", 0.0, 0.5, False)]
    arm("uma linha so com a palavra suspeita nao publica nada",
        captions(partials(chunks, emit_partial=True)),
        captions(drive_control(chunks, emit_partial=True)),
        [])

    # ── arm 6: a linha FECHADA sai com a palavra toda ──────────────────────
    # O historico tem a frase completa: a regra e sobre o PARCIAL.
    f = W.LineFormer(emit_partial=True)
    shown = []
    for text, s, e, cont in [("eu vou", 0.0, 0.5, False), ("cantar", 0.5, 1.0, False)]:
        shown += f.push(text, s, e, continues=cont)
    shown += f.flush()
    closed = W.line_events(f.take_closed())
    arm("a linha fechada sai com a palavra toda",
        captions(closed),
        captions(drive_control([("eu vou", 0.0, 0.5, False),
                                ("cantar", 0.5, 1.0, False)], emit_partial=True)),
        ["eu vou cantar"])

    # ── arm 7: a regra e INDEPENDENTE DA LINGUA ─────────────────────────────
    # As MESMAS formas, em varias linguas. O que muda e a PALAVRA; o que nao
    # muda e o COMPORTAMENTO. Se a regra dependesse do dicionario, um destes
    # arms daria um resultado diferente.
    #
    # O ESPERADO e o texto SEM a ultima palavra, e o texto INTEIRO quando o
    # fragmento seguinte PROVA que a palavra acabou (o veredicto `continues` a
    # FALSO). Com `continues=True` a palavra continua a crescer e fica fora.
    linguas = [
        ("eu so", "u", True),                 # pt: "so" -> "sou"/"sozinho"
        ("I am", "here", True),               # en: word boundary at the space
        ("я де", "ла", True),                 # ru: cyrillic, no `▁`
        ("él es", "t", True),                 # es: accented
        ("hola", "que", True),                # es: short first word
    ]
    for texto, seguinte, cont in linguas:
        chunks = [(texto, 0.0, 0.5, False), (seguinte, 0.5, 1.0, cont)]
        estavel = captions(partials(chunks, emit_partial=True))
        # A palavra final da PRIMEIRA linha fica fora; o resto aparece.
        esperado = [texto.rsplit(" ", 1)[0]] if " " in texto else []
        arm(f"a regra e a mesma em qualquer lingua ({texto!r})",
            estavel,
            captions(drive_control(chunks, emit_partial=True)),
            esperado)

    # ── arm 8: o texto estavel e um PREFIXO do texto completo ──────────────
    # NADA SE PERDE: o estavel e sempre o inicio do completo.
    chunks = [("a b c", 0.0, 0.5, False), ("d e", 0.5, 1.0, False)]
    estavel = captions(partials(chunks, emit_partial=True))
    completo = W.join_fragments([("a b c", False), ("d e", False)])
    ok = all(t == completo[:len(t)] for t in estavel)
    arm("o texto estavel e um prefixo do texto completo (nada se perde)",
        ok,
        False,
        True,
        control_must_differ=False)

    # ── arm 9: o texto estavel NUNCA encolhe ───────────────────────────────
    # O que o dono le e um texto que so cresce. Um encolhimento seria uma
    # palavra a desaparecer do ecra -- o oposto do pedido.
    chunks = [("a b", 0.0, 0.5, False), ("c d", 0.5, 1.0, False), ("e", 1.0, 1.5, False)]
    estavel = captions(partials(chunks, emit_partial=True))
    ok = all(estavel[i].startswith(estavel[i - 1]) for i in range(1, len(estavel)))
    arm("o texto estavel nunca encolhe",
        ok,
        False,
        True,
        control_must_differ=False)

    # ── arm 10: uma palavra ja provada nao volta a desaparecer ────────────
    # A PROPRIEDADE: o conjunto de palavras que o dono ja viu so CRESCE. Uma
    # palavra que apareceu uma vez nao pode desaparecer do ecra -- o oposto
    # do pedido, e a coisa que faria a legenda "tremer".
    #
    # A primeira parcial e "eu" (a palavra "vou" ainda nao esta provada), a
    # segunda e "eu vou" (agora esta), a terceira e "eu vou cantar". A
    # palavra "vou" aparece na segunda e fica nas seguintes.
    chunks = [("eu vou", 0.0, 0.5, False), ("cantar", 0.5, 1.0, False),
              ("agora", 1.0, 1.5, False)]
    estavel = captions(partials(chunks, emit_partial=True))
    vistas = set()
    ok = True
    for t in estavel:
        novas = set(t.split())
        if not vistas <= novas:
            ok = False
        vistas = novas
    arm("uma palavra ja provada nao volta a desaparecer",
        ok,
        False,
        True,
        control_must_differ=False)

    # ── arm 11: o PAINEL nao segura uma segunda palavra ────────────────────
    # O worker ja segurou a palavra suspecta e marcou o evento com
    # `stable: true`. O painel tambem segura a ultima da cauda (o hold-back do
    # LocalAgreement-2) -- e se as DUAS camadas segurassem, o dono perderia
    # DUAS palavras do ecra, o dobro do que pediu.
    #
    # Este arm corre o `app/panel/panel.js` REAL: nao copia a expressao, nao
    # reimplementa o hold-back. Le a linha do painel que decide o que e
    # PINTA (`wordsAreWhole` / `shownProv`), aplica-a aos words do motor REAL
    # (`caption-formulation.js`), e o resultado e o que o dono veria.
    #
    # O painel e um IIFE de DOM: nao se corre. O que se corre e a EXPRESSAO
    # que ele le, extraida do ficheiro vivo -- se o painel mudar a regra, este
    # arm muda com ele (e falha), em vez de continuar a medir uma copia
    # parada.
    try:
        import json as _json
        import re as _re
        import subprocess as _sp
        _panel_js = os.path.join(REPO, "app", "panel", "caption-formulation.js")
        _stable_js = os.path.join(REPO, "app", "panel", "stable-words.js")
        _panel_view = os.path.join(REPO, "app", "panel", "panel.js")
        with open(_panel_view, encoding="utf-8") as _fh:
            _src = _fh.read()
        # A EXPRESSAO VIVA do painel: as duas linhas que decidem o que e
        # pintado. Se o painel as mudar, este arm muda com ele.
        _m = _re.search(
            r"const wordsAreWhole = (.*?);\s*\n\s*const shownProv = (.*?);",
            _src, _re.S)
        if not _m:
            raise RuntimeError("a expressao do painel nao foi encontrada em panel.js")
        _expr_words, _expr_shown = _m.group(1), _m.group(2)
        _probe = (
            "require(%s);"
            "global.StableWords=require(%s);"
            "const S=require(%s);"
            "const fs=require('fs');"
            "const src=fs.readFileSync(%s,'utf8');"
            "const m=src.match(/const wordsAreWhole = (.*?);\\s*\\n\\s*const shownProv = (.*?);/s);"
            "if(!m) throw new Error('expressao nao encontrada');"
            "if(!/StableWords\\.wrap\\(/.test(src)) throw new Error('o painel nao embrulha o motor');"
            "let out=[];"
            "const e=StableWords.wrap(S.createEngine({onCommit:()=>{},onProvisional:(c,p)=>{"
            "  const tailClosed=!!e.state().tailClosed;"
            "  const key=null;"
            "  const wordsAreWhole=eval(m[1]);"
            "  const provWords=p.map(t=>t.w);"
            "  const shownProv=eval(m[2]);"
            "  out.push(shownProv);}}));"
            "e.ingest('eu vou',{start:0.0,end:0.5,stable:true});"
            "e.ingest('eu vou cantar',{start:0.5,end:1.0,stable:true});"
            "console.log(JSON.stringify(out));"
        ) % (_json.dumps(_stable_js), _json.dumps(_stable_js), _json.dumps(_panel_js),
             _json.dumps(_panel_view))
        _r = _sp.run(["node", "-e", _probe], capture_output=True, text=True, timeout=120)
        if _r.returncode != 0:
            raise RuntimeError(_r.stderr.strip()[-400:])
        pintado = _json.loads(_r.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001
        pintado = "<erro: %r>" % (exc,)
    arm("o painel nao segura uma segunda palavra (o worker ja segurou)",
        pintado,
        [["eu"], ["eu", "vou"]],
        [["eu", "vou"], ["eu", "vou", "cantar"]])

    # ── A PROVA POR TOKEN (segunda metade da ordem, 2026-10-30) ────────────
    # O dono, verbatim, quando a primeira cura ficou a espera:
    #   *"'CAUS' QUANDO O FALANTE FALA 'CAUSE LIKE'. E AÍ DA DISPLAY NO 'CAUSE
    #   LIKE' SOMENTE APOS A PROXIMA PALAVRA DELE, QUE LEVOU UNS SEGUNDOS PRA
    #   ELE FALAR."*
    # A regra de espaco escondia a palavra ja provada. A regra do MARCADOR
    # esconde so' a cauda aberta, e a prova chega com o token seguinte.
    import stable_words as S  # noqa: PLC0415 -- o modulo do worker, ja no path

    prov, tail = S.proven_text([("▁CAUS", False)])
    arm("'CAUS' sozinho nao tem NADA provado (o pedaco dele nao vai para o ecra)",
        prov, "CAUS", "")

    prov, tail = S.proven_text([("▁CAUSE LIKE", False)])
    arm("'CAUSE LIKE' publicado ate' CAUSE no INSTANTE em que LIKE e' decodificado",
        (prov, tail), ("▁CAUSE LIKE", ""), ("▁CAUSE", "LIKE"))

    prov, tail = S.proven_text([("▁CAUS", False), ("E", True)])
    arm("a palavra que ATRAVESSA a fronteira do chunk fica provada de uma vez",
        tail, "E", "▁CAUSE")

    prov, tail = S.proven_text([("▁a b c", False)])
    arm("a cauda e' SO' a ultima palavra, nunca as duas ultimas",
        (prov, tail), ("▁a b c", ""), ("▁a b", "c"))

    publicar, transportar = S.close_parts([("▁hello wor", False)], carry=False)
    arm("fecho por SILENCIO publica a linha inteira (o audio provou a palavra)",
        (publicar, transportar), ("▁hello", "wor"), (None, ""))

    publicar, transportar = S.close_parts([("▁hello wor", False)], carry=True)
    arm("fecho por TETO publica o provado e TRANSPORTA a cauda para a seguir",
        (publicar, transportar), (None, ""), ("▁hello", "wor"))

    arm("o texto com espaco final nao e' devolvido INTEIRO (bug de 2026-10-30)",
        S.stable_text("hello wor "), "hello wor ", "hello")

    # ── O TRANSPORTE, EXERCITADO NO `LineFormer` VIVO ──────────────────────
    # Uma linha que fecha pelo TETO de caracteres corta a meio: a cauda nao
    # provada tem de reaparecer como primeiro fragmento da linha SEGUINTE, e nao
    # de ser publicada nem perdida.
    try:
        f = W.LineFormer(max_chars=24, min_chars=1, emit_partial=True)
        evs = []
        evs += f.push("▁alpha bravo charlie delta", 0.0, 1.0)
        evs += f.push("▁echo foxtrot", 1.0, 2.0)
        abertas = [str(t) for t, _c in (f._words or ())]
        trasportou = bool(abertas) and abertas[0].lstrip("▁").startswith("")
        depois = f.line()
    except Exception as exc:  # noqa: BLE001
        abertas, trasportou, depois = ["<erro %r>" % (exc,)], False, ""
    arm("a linha seguinte comeca pelo texto transportado, nao pelo vazio",
        bool(trasportou), False, True)

    # ── A CAUDA PROVADA PELO SILENCIO (2026-11-04) ──────────────────────────
    # MEDIDO no log vivo do dono (191 pinturas que MUDARAM o texto): a primeira
    # aparicao e' bimodal -- p50 195 ms, e 45% a 1500 ms+, que e' exatamente a
    # valvula `COMMIT_MAX_HOLD_MS` do painel. O bloco de audio que vem depois
    # das ultimas palavras decodifica VAZIO, logo `push` nunca corre e a cauda
    # nao provada ficava a espera do relogio do painel. `publish_on_silence`
    # publica a linha inteira, `stable`, ao fim de `TAIL_SILENCE_CLOSE_S`.
    f2 = W.LineFormer(min_chars=1, emit_partial=True)
    f2.push("hello wor", 0.0, 1.5, continues=True)
    curto = f2.publish_on_silence(2.0)
    provado = f2.publish_on_silence(2.4)
    repetido = f2.publish_on_silence(3.0)
    # O CONTROLE: a mesma linha, com o limiar do silencio posto acima de tudo o
    # que este arm mede -- e' a implementacao de ANTES (o silencio nao publica).
    # O limiar vive em `worker/silence_tail.py` e e' MUTADO aqui, nao copiado.
    f3 = W.LineFormer(min_chars=1, emit_partial=True)
    f3.push("hello wor", 0.0, 1.5, continues=True)
    _tail = W._silence_tail()
    _limiar = _tail.SILENCE_PROVE_S
    try:
        _tail.SILENCE_PROVE_S = 99.0
        antes = f3.publish_on_silence(2.4)
    finally:
        _tail.SILENCE_PROVE_S = _limiar
    arm("silencio curto NAO publica; 0,9 s de silencio publica a linha inteira e `stable`",
        ([e["text"] for e in curto],
         [(e["text"], bool(e.get("stable"))) for e in provado]),
        ([], []),
        ([], [("hello wor", True)]))
    arm("o MESMO silencio publica uma vez, nunca a cada bloco",
        [e["text"] for e in repetido], ["hello wor"], [])
    # A linha continua ABERTA: o silencio prova a cauda, nao fecha a frase
    # (`SENTENCE_GAP_S = 8.0` e' quem decide onde a LINHA quebra). A fala que
    # segue JA estava a vista ("hello wor"), por isso o unico fragmento novo
    # ("world") fica retido pela regra da palavra -- nada a repintar.
    mais = f2.push("world", 2.4, 3.5, continues=False)
    arm("depois da publicacao a linha continua a mesma (nao fechou)",
        ([e["text"] for e in mais], f2.line()), (["fechada"], "hello wor"),
        ([], "hello wor world"))

    failed = RESULTS.count(False)
    print(f"incomplete-word-oracle: {len(RESULTS) - failed} PASS / {failed} FAIL "
          f"({len(RESULTS)} arms)  impl={W.__file__}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
