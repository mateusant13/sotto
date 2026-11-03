"""Portao da SEGUNDA FONTE da legenda do YouTube (`youtube_cdp_source.py`).

POR QUE ESTE FICHEIRO EXISTE

Com a aba do YouTube em segundo plano o Chrome deixa de expor a legenda na arvore
de acessibilidade (medido 2026-11-03: 3 minutos com um unico `YOUTUBE_CAPTION`, e
um cliente UIA novo noutro processo tambem vazio). A CDP le' o DOM do player e
resolve isso -- mas um caminho novo sem portao e' uma promessa. Estas arms
EXECUTAM as decisoes reais do modulo, nao procuram texto:

  A1 linhas      -- a resposta da pagina vira LINHAS do player, com a geometria de
                    cada filho; uma linha sem texto nao e' linha.
  A2 lixo        -- JSON invalido, lista, `null`: None. Nunca uma linha inventada.
  A3 identidade  -- com o id do video declarado, so' essa aba; com DUAS abas e sem
                    id, `ambiguous` (nunca se adivinha qual video esta' no ecra).
  A4 relogio     -- `t`/`paused` do `video.currentTime` chegam ao consumidor e um
                    `t` que nao e' numero vira None, nunca 0.0.
  A5 recorte     -- a expressao que corre na pagina recorta as linhas pelo
                    `overflow: hidden` do `.caption-window` (as que rolaram para
                    fora continuam no DOM e nao estao no ecra).
  A6 sem-foco    -- NINGUEM pede `Emulation.setFocusEmulationEnabled`: medido lado
                    a lado (20 leituras cada), ele leva a mediana de 2-5 ms para
                    108 ms e o p90 para 5 s -- o instrumento a criar a lentidao que
                    depois mede.
  A7 um-produtor -- a shell marca a pintura como fresca quando a leitura devolve
                    linhas, para o re-render da faixa a 60 ms nao alternar com ela
                    no mesmo ecra.

`--neg-arm` muta uma COPIA do modulo em tres sitios e exige que as arms
correspondentes caiam. Sem isso o portao seria uma lista de verdades sobre si
mesmo.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, '..', 'app', 'webview')
MODULE = os.path.join(APP, 'youtube_cdp_source.py')
SHELL = os.path.join(APP, 'sotto_webview.py')
INSTRUMENT = os.path.join(HERE, '_yt-live-latency.py')


def _load(path, name):
    import importlib.util as _iu
    spec = _iu.spec_from_file_location(name, path)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    return io.open(path, encoding='utf-8', errors='replace').read()


def arms(module_path=MODULE, shell_path=SHELL, instrument_path=INSTRUMENT):
    mod = _load(module_path, 'yt_cdp_under_test')
    shell = _read(shell_path)
    out = []

    # A1 -- linhas
    payload = ('{"videoId":"abc","title":"t","why":"painted","rows":['
               '{"text":"  ola   mundo ","items":['
               '{"text":"ola","left":"10.6","top":5,"right":20,"bottom":15},'
               '{"text":"mundo","left":25,"top":5.4,"right":40,"bottom":15}]},'
               '{"text":"   ","items":[{"text":"x","left":1,"top":1,"right":2,"bottom":3}]}]}')
    snap = mod.parse_snapshot(payload)
    a1 = (snap is not None and snap["rows"] == ["ola mundo"]
          and [i["text"] for i in snap["items"]] == ["ola", "mundo"]
          and snap["items"][0]["left"] == 10)
    out.append(("linhas-do-player", a1, "rows=%r" % (snap or {}).get("rows")))

    # A2 -- lixo
    a2 = (mod.parse_snapshot("nao e json") is None
          and mod.parse_snapshot("[]") is None
          and mod.parse_snapshot("null") is None)
    out.append(("sem-linha-inventada", a2, "lixo=None"))

    # A3 -- identidade
    tabs = [{"url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
             "webSocketDebuggerUrl": "ws1"},
            {"url": "https://www.youtube.com/watch?v=BBBBBBBBBBB",
             "webSocketDebuggerUrl": "ws2"}]
    pick_named, why_named = mod.pick_target(tabs, "BBBBBBBBBBB")
    pick_amb, why_amb = mod.pick_target(tabs, "")
    pick_absent, why_absent = mod.pick_target(tabs, "CCCCCCCCCCC")
    a3 = (pick_named is tabs[1] and why_named == "named"
          and pick_amb is None and why_amb == "ambiguous"
          and pick_absent is None and why_absent == "video-not-open")
    out.append(("identidade-do-video", a3,
                "%s/%s/%s" % (why_named, why_amb, why_absent)))

    # A4 -- relogio
    snap2 = mod.parse_snapshot('{"t": 34.571, "paused": true, "rows": []}')
    snap3 = mod.parse_snapshot('{"t": "abc", "paused": null, "rows": []}')
    a4 = (snap2["t"] == 34.571 and snap2["paused"] is True
          and snap3["t"] is None and snap3["paused"] is None)
    out.append(("relogio-do-player", a4, "t=%r/%r" % (snap2["t"], snap3["t"])))

    # A5 -- recorte do clip
    js = mod.EXTRACT_JS
    a5 = ("overflowY" in js and "0.5 * h" in js and "getBoundingClientRect" in js)
    out.append(("recorte-do-clip", a5, "half-line=%s" % ("0.5 * h" in js)))

    # A6 -- sem focus emulation em sitio nenhum do produto
    # So' CODIGO conta: o comentario do instrumento e' a medicao que justifica a
    # regra (mediana 2-5 ms sem ele, 108 ms com ele) e tem de sobreviver a ela.
    offenders = []
    for path in (shell, instrument_path, MODULE):
        if not os.path.exists(path):
            continue
        text = _read(path)
        for match in re.finditer(r"\(\s*['\"]Emulation\.setFocusEmulationEnabled['\"]"
                                 r"|\.setFocusEmulationEnabled\s*\(", text):
            # So' a TUPLA ou a CHAMADA contam. A prosa (docstring, comentario) que
            # cita o nome para explicar a medicao nao e' um pedido a ninguem.
            line = text[:match.start()].rsplit(nl, 1)[-1]
            if line.lstrip().startswith(('#', '*', '"""', "'''")):
                continue
            offenders.append(os.path.basename(path))
            break
    a6 = not offenders
    out.append(("sem-focus-emulation", a6, "offenders=%s" % (offenders or "-")))

    # A7 -- um produtor por vez
    a7 = bool(re.search(r"if lines:\s*\n\s*self\.yt_live_paint_at = "
                        r"time\.monotonic\(\)", shell))
    out.append(("um-produtor-por-vez", a7, "marca-fresca=%s" % a7))
    return out


def neg_arm():
    """Tres mutacoes numa COPIA do modulo; cada uma derruba a SUA arm."""
    tmp = tempfile.mkdtemp(prefix="yt-cdp-neg-")
    try:
        src = _read(MODULE)
        results = []

        mut = os.path.join(tmp, "sem_id.py")
        io.open(mut, "w", encoding="utf-8").write(
            src.replace('    if video_id:\n        named = [t for t in tabs if video_id in str(t.get("url") or "")]',
                        '    if False:\n        named = [t for t in tabs if video_id in str(t.get("url") or "")]', 1))
        got = dict((n, ok) for n, ok, _ in arms(module_path=mut))
        results.append(("identidade-cega", not got.get("identidade-do-video", False)))

        mut2 = os.path.join(tmp, "sem_clip.py")
        io.open(mut2, "w", encoding="utf-8").write(
            src.replace("    return ov >= 0.5 * h;", "    return true;", 1))
        got2 = dict((n, ok) for n, ok, _ in arms(module_path=mut2))
        results.append(("clip-removido", not got2.get("recorte-do-clip", False)))

        mut3 = os.path.join(tmp, "linha_sem_texto.py")
        io.open(mut3, "w", encoding="utf-8").write(
            src.replace('        text = " ".join(str(line.get("text") or "").split())\n        if not text:\n            continue',
                        '        text = str(line.get("text") or "")\n        if False:\n            continue', 1))
        got3 = dict((n, ok) for n, ok, _ in arms(module_path=mut3))
        results.append(("linhas-sem-filtro", not got3.get("linhas-do-player", False)))
        return results
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)
    if args.neg_arm:
        results = neg_arm()
        bad = 0
        for name, caught in results:
            print("NEG-ARM %-20s %s" % (name, "CAUGHT" if caught else "NOT-CAUGHT"))
            bad += 0 if caught else 1
        print("NEG-ARM VERDICT: %s (%d/%d)"
              % ("PASS" if not bad else "FAIL", len(results) - bad, len(results)))
        # A CONVENCAO DA BATERIA (2026-11-03): um `red-as-expected` declara rc=1.
        # "Apanhei todos os mutantes" E' o resultado VERMELHO que o `:expectred`
        # exige, senao o passo passa como se fosse um oraculo normal e o mutante
        # nunca e' recusado. rc=0 quando um mutante escapa (o passo fica vermelho
        # de verdade, e com a frase FAIL no log).
        return 1 if not bad else 0
    bad = 0
    for name, ok, note in arms():
        print("%-22s %s  %s" % (name, "PASS" if ok else "FAIL", note))
        bad += 0 if ok else 1
    print("VERDICT: %s (%d/%d)"
          % ("PASS" if not bad else "FAIL", 7 - bad, 7))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
