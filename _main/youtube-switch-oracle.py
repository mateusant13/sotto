#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-10-30 -- *"trocar de video
# tambem demora pra caralho pra aparecer a legenda"*. Nao corrige defeito
# nenhum: mede que a troca de faixa custa UMA extracao de metadados e nao duas,
# com uma rede FALSA (este oraculo nao faz um unico pedido ao YouTube).
"""ORACLE: A TROCA DE LEGENDA CUSTA UMA EXTRACAO, NAO DUAS.

O DEFEITO MEDIDO no log do dono (`_main/webview-run.log`, troca das 04:40:02):

    04:40:02.601 YOUTUBE_VIDEO_CHANGED            <- ele trocou de video
    04:40:08.097 YOUTUBE_TRACK_READY lang=en-orig <- 5,5 s, extracao #1
    04:40:08.664 YOUTUBE_TRACK_STATE painted-other-track
    04:40:29.126 YOUTUBE_TRACK_READY lang=pt-orig <- +20 s, extracao #2
    04:40:29.456 YOUTUBE_CAPTION                  <- 27 s de nada no ecra

O pintado do player decide a faixa (`fetch_track(..., painted=...)`), mas a
primeira chamada acontece antes de haver pintura: a preferencia escolhe
`en-orig`, o pintado depois diz que e' `pt-orig`, e a re-escolha repetia o
`yt-dlp` inteiro (5,0 s medidos por chamada). A LISTA DE CANDIDATOS passa a ser
guardada, e a re-escolha so' volta a pedir os KB de cada payload.

O QUE E' MEDIDO, com a rede trocada por uma funcao que conta:
  1. a primeira escolha extrai UMA vez;
  2. a re-escolha pelo pintado serve a OUTRA lingua e NAO extrai;
  3. a mesma pergunta outra vez nao extrai nada (cache);
  4. o NEGATIVO: com a reutilizacao desligada, a re-escolha extrai outra vez
     -- e e' isso que o oraculo tem de ver (senao nao tem dentes).

Uso:
    python _main/youtube-switch-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/youtube-switch-oracle.py --neg-arm  -> muta uma COPIA e exige RED
"""
from __future__ import annotations

import importlib.util as _ilu
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("SOTTO_ROOT") or r"H:\sotto").resolve()
WEBVIEW = ROOT / "app" / "webview"
EXIT_PASS, EXIT_FAIL = 0, 1
VIDEO = "A-CZBCTG29M"

rows: list[tuple[bool, str, str]] = []

#: As duas linhas do mesmo video, em duas linguas. O pintado do player tem de
#: casar com UMA delas e nao com a outra -- e' o que faz a re-escolha existir.
EN_CUES = [
    {"start": 0.0, "end": 2.0, "text": "Have you ever had"},
    {"start": 2.0, "end": 4.0, "text": "to kill a man?"},
]
PT_CUES = [
    {"start": 0.0, "end": 2.0, "text": "Voce ja teve que"},
    {"start": 2.0, "end": 4.0, "text": "matar um homem?"},
]


def add(ok, name, detail=""):
    rows.append((bool(ok), name, detail))


def verdict(name):
    passed = sum(1 for ok, _, _ in rows if ok)
    total = len(rows)
    failed = total - passed
    for ok, label, detail in rows:
        if not ok:
            print(f"FALHA: {label}" + (f"  -- {detail}" if detail else ""))
    print(f"\n{name} {'GREEN' if not failed else 'VERMELHO'} -- "
          f"arms={total} pass={passed} fail={failed} "
          f"(rc={EXIT_PASS if not failed else EXIT_FAIL})")
    return EXIT_PASS if not failed else EXIT_FAIL


def json3(cues):
    """Um payload json3 minimo, na forma que `parse_json3` le'."""
    events = [{"tStartMs": int(c["start"] * 1000),
               "dDurationMs": int((c["end"] - c["start"]) * 1000),
               "segs": [{"utf8": c["text"]}]} for c in cues]
    return json.dumps({"events": events})


EN_URL = "https://fake.invalid/en-orig.json3"
PT_URL = "https://fake.invalid/pt-orig.json3"


def load_module(cache_dir):
    sys.path.insert(0, str(WEBVIEW))
    spec = _ilu.spec_from_file_location("yc_switch", str(WEBVIEW / "youtube_captions.py"))
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CACHE_DIR = str(cache_dir)
    calls = {"extract": 0, "http": 0}

    info = {
        "duration": 120.0,
        # A LINGUA DO VIDEO e' o que faz a politica servir INGLES primeiro
        # (regra do dono: ingles, excepto espanhol). Sem este campo a ordem e'
        # outra e o caso medido no log dele nao se reproduz.
        "language": "pt",
        "subtitles": {},
        "automatic_captions": {
            "en-orig": [{"ext": "json3", "url": EN_URL}],
            "pt-orig": [{"ext": "json3", "url": PT_URL}],
        },
    }

    def fake_extract(video_id, timeout):
        calls["extract"] += 1
        return dict(info)

    def fake_http(url, timeout):
        calls["http"] += 1
        if "pt-orig" in str(url):
            return json3(PT_CUES)
        return json3(EN_CUES)

    module._extract_info = fake_extract
    module._http_get = fake_http
    # A leitura do player nao existe aqui: nada de UIA num oraculo.
    module._resolve_player_track = lambda vid, lang: ("", {"known": False})
    return module, calls


def run(module=None) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="switch-cache-"))
    try:
        yc, calls = load_module(tmp)
        painted_pt = "Voce ja teve que matar um homem?".split()

        print("ARM 1 -- a primeira escolha (ainda sem pintura) extrai UMA vez")
        first = yc.fetch_track(VIDEO, painted=None)
        add(first.get("state") == "has-track", "a primeira escolha serve uma faixa",
            str(first.get("state")) + " lang=" + str(first.get("lang")))
        add(calls["extract"] == 1, "uma extracao", f"extract={calls['extract']}")

        print("\nARM 2 -- a re-escolha pela PINTURA serve a outra lingua sem extrair")
        before = calls["extract"]
        second = yc.fetch_track(VIDEO, painted=painted_pt)
        add(second.get("state") == "has-track", "a re-escolha serve uma faixa",
            str(second.get("state")))
        add(str(second.get("lang")) == "pt-orig",
            "e a faixa e' a que o player pinta (pt-orig)",
            f"lang={second.get('lang')} (antes={first.get('lang')})")
        add(calls["extract"] == before,
            "a re-escolha NAO volta a extrair metadados",
            f"extract={calls['extract']} (antes={before})")
        add(any('Voce ja teve' in str(c.get("text")) for c in (second.get("cues") or [])),
            "as cues servidas sao as da lingua pintada",
            str([c.get("text") for c in (second.get("cues") or [])])[:70])

        print("\nARM 3 -- a mesma pergunta outra vez nao extrai nada")
        before = calls["extract"]
        third = yc.fetch_track(VIDEO, painted=painted_pt)
        add(calls["extract"] == before and bool(third.get("cached")),
            "terceira chamada sai do CACHE", f"cached={third.get('cached')} "
            f"extract={calls['extract']}")

        print("\nARM 4 -- o candidato reutilizado e' o que o `tracks_from_info` deu")
        arm_no_blackout()
        # RE-ANCORADO A 2026-10-30, com a razao escrita: `>= 2` era o mundo anterior a
        # regra do dono de hoje (*"legendas nao traduzem entre ingles pt br e espanhol.
        # so outras linguas, todas pro ingles"*). Num video PORTUGUES a politica agora
        # devolve UMA chave -- a portuguesa, porque PT nunca se traduz -- logo o
        # comprimento 1 e' a CONSEQUENCIA correcta, nao uma regressao. O braco guarda a
        # propriedade: a lista existe, nao esta' vazia, e e' a que o `tracks_from_info`
        # deu (a primeira chave e' a que o resultado serviu).
        cands = first.get("candidates")
        add(isinstance(cands, list) and len(cands) >= 1
            and cands[0].get("lang") == (first.get("lang") or cands[0].get("lang")),
            "a lista de candidatos fica guardada e a primeira e' a servida",
            str([c.get('lang') for c in (cands or [])]))
        return verdict("YOUTUBE-SWITCH")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def arm_no_blackout() -> None:
    """A troca de faixa NAO devolve o vazio durante a re-escolha.

    O DEFEITO MEDIDO (log do dono, 04:40:02): 20 s sem nada no ecra enquanto a
    faixa certa era re-escolhida. O que NAO pode ser a cura e' mostrar as
    palavras da faixa que o PLAYER pinta quando ela nao e' a servida: ele
    proibiu a traducao (*"para de traduzir pra pt br do ingles e do espanhol"*),
    e as palavras pintadas nesse caso sao a traducao. O conserto e' o custo --
    UMA extracao, medido acima. Este braco fixa a PROIBICAO para ninguem a
    "resolver" outra vez mostrando a lingua errada.
    """
    print("\nARM 5 -- o ramo `painted-other-track` NAO mostra a lingua pintada")
    import ast as _ast
    src = (WEBVIEW / "sotto_webview.py").read_text(encoding="utf-8")
    body = None
    for node in _ast.parse(src).body:
        if isinstance(node, _ast.ClassDef):
            for item in node.body:
                if isinstance(item, _ast.FunctionDef) and item.name == "_youtube":
                    body = _ast.get_source_segment(src, item)
    add(bool(body), "_youtube extraido do ficheiro que corre")
    if not body:
        return
    # O MARCADOR E' O COMENTARIO QUE ABRE O RAMO, e nao a string
    # `painted-other-track`: ela aparece dentro do ramo do `track is None`
    # (onde mostrar o pintado E' correcto, porque nao ha' faixa servida) e o
    # braco passava a olhar para o sitio errado.
    start = body.find("THE PLAYER IS PAINTING ANOTHER TRACK")
    add(start >= 0, "o ramo existe no ficheiro")
    branch = body[start:] if start >= 0 else ""
    add("paint_line" not in branch,
        "o ramo nao devolve `paint_line(painted)` (a lingua pintada nao vai ao ecra)")
    add("_yt_lines" in branch or "cue_at" in branch,
        "o ramo desenha a FAIXA SERVIDA, no relogio do player")


def neg_arm() -> int:
    """Muta uma COPIA: a lista de candidatos deixa de ser reutilizada."""
    global WEBVIEW
    tmp = Path(tempfile.mkdtemp(prefix="switch-neg-"))
    try:
        copy = tmp / "app" / "webview"
        copy.mkdir(parents=True)
        # O braco 5 executa `_youtube` do ficheiro que corre: o shell tem de ir
        # na copia, senao o mutante e' medido num ficheiro que nao existe.
        for name in ("youtube_captions.py", "sotto_webview.py",
                     "youtube_window.py", "youtube_reveal.py"):
            shutil.copy2(WEBVIEW / name, copy / name)
        target = copy / "youtube_captions.py"
        text = target.read_text(encoding="utf-8")
        # O MUTANTE TEM DE ATINGIR OS DOIS CAMINHOS QUE POUPAM A EXTRACAO.
        # MEDIDO 2026-10-30: mutar so' `CANDIDATE_TTL_S` ficou **INERT** e o
        # braco negativo publicava rc=0 ("o oraculo NAO ve a regressao"). A
        # razao esta' no produto: a SEGUNDA chamada com o pintado nao chega ao
        # ramo que consulta esse TTL -- ela e' servida pelo cache FRESCO
        # (`cached = _cache_read(vid)`, ~l.1197), que nao olha para constante
        # nenhuma. Quem poupa a extracao sao DOIS sitios: o cache fresco e a
        # lista de candidatos. O mutante desliga os dois, e exige que cada
        # ancoragem morda -- um mutante que nao encontra o texto nao e' um
        # controlo, e' um passo em branco.
        mutant = text.replace("cached = _cache_read(vid)",
                              "cached = None  # MUTANTE")
        if mutant == text:
            print("NEG-ARM: nao consegui mutar o cache fresco (o texto mudou)")
            return EXIT_FAIL
        nxt = mutant.replace(
            "reused = _rerank_reused(cands, lang_prefs, plang, older)",
            "reused = None  # MUTANTE")
        if nxt == mutant:
            print("NEG-ARM: nao consegui mutar a lista de candidatos "
                  "(o texto mudou)")
            return EXIT_FAIL
        target.write_text(nxt, encoding="utf-8")
        # A SEGUNDA REGRESSAO: as palavras pintadas deixam de ir para o ecra.
        print("NEG-ARM: nem o cache fresco nem a lista de candidatos servem (2 extracoes)")
        saved = WEBVIEW
        WEBVIEW = copy
        try:
            rc = run()
        finally:
            WEBVIEW = saved
        if rc == EXIT_FAIL:
            print("\nNEG-ARM PASS -- RED as designed: o mutante derruba o oraculo")
            return EXIT_FAIL
        print("\nNEG-ARM FAIL -- o oraculo NAO ve a regressao")
        return EXIT_PASS
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv) -> int:
    if "--neg-arm" in argv:
        return neg_arm()
    return run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
