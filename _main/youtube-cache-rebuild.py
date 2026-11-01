#!/usr/bin/env python
"""RE-CONSTRUIR UMA ENTRADA DA CACHE A PARTIR DO PAYLOAD JA CAPTURADO -- com proveniencia.

PORQUE ESTE FICHEIRO EXISTE, e o que ele NAO e:

  * A cache `_cache/youtube-captions/<video>.jsonl` deste video foi escrita em 2026-10-22, antes
    de o cue carregar o RELOGIO DA REVELACAO (`words`, o `tOffsetMs` do payload). A entrada esta
    no formato actual (`schema: 3`) e e legivel: o que lhe falta e so o relogio, e sem ele o
    Sotto pinta a linha inteira de uma vez. Reconstrui-la acrescenta o relogio e nada mais.
  * O payload de onde ela e reconstruida foi CAPTURADO DO PROPRIO PLAYER em 2026-10-22
    (`_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3`, sha256 impresso abaixo) e a entrada antiga e,
    campo a campo, o `parse_json3` desse payload -- este script CONFERE isso antes de escrever e
    recusa-se a escrever quando os dois divergem.
  * `fetched_at` NAO se inventa: fica o instante da recolha original. O que se acrescenta e
    `rebuilt_from` / `rebuilt_at` / `rebuilt_note`, para a entrada nunca se fazer passar por
    uma recolha fresca.

O que muda na entrada: o formato (`schema: 3`) e o relogio da revelacao (`words` em cada cue,
com o `tOffsetMs` do payload). Nada mais -- `lang`, `player_*`, `duration`, `ext` ficam como
estavam.

    python _main\\youtube-cache-rebuild.py --video WdaHAGRBB6s
    python _main\\youtube-cache-rebuild.py --video WdaHAGRBB6s --check   # so compara

Exit: 0 escrito (ou ja igual), 2 payload ausente, 3 recusa (a entrada nao e o parse do payload).
"""
# NO-BUG: migracao da entrada de cache de 2026-10-22 para o formato com o relogio da revelacao;
# nao corre na app e recusa escrever quando a entrada antiga nao e o parse do payload.
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))


def campos(cue):
    return (round(float(cue.get("start")), 3), round(float(cue.get("end")), 3),
            str(cue.get("text") or ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description="reconstruir uma entrada da cache a partir do payload")
    ap.add_argument("--video", default="WdaHAGRBB6s")
    ap.add_argument("--fixture", default=None)
    ap.add_argument("--check", action="store_true", help="comparar e sair, sem escrever")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    import youtube_captions as yc

    fixture = args.fixture or os.path.join(HERE, "fixtures", "yt-%s.en-orig.json3" % args.video)
    if not os.path.isfile(fixture):
        print("PAYLOAD AUSENTE: %s -- nada a reconstruir" % fixture)
        return 2
    raw = io.open(fixture, encoding="utf-8").read()
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    novos = yc.parse_json3(raw)
    if not novos:
        print("PARSE VAZIO: o payload nao deu cue nenhum -- nada a escrever")
        return 3

    path = yc._cache_path(args.video)
    if not os.path.isfile(path):
        print("CACHE AUSENTE: %s -- este script reconstrói, nao inventa uma recolha" % path)
        return 2
    velho = json.loads(io.open(path, encoding="utf-8").read().strip() or "{}")

    antigos = velho.get("cues") or []
    if len(antigos) != len(novos):
        print("RECUSA: a entrada tem %d cues e o payload da %d -- nao e a mesma faixa"
              % (len(antigos), len(novos)))
        return 3
    for a, b in zip(antigos, novos):
        if campos(a) != campos(b):
            print("RECUSA: um cue diverge da entrada para o payload: %r != %r"
                  % (campos(a), campos(b)))
            return 3

    com_relogio = sum(1 for c in novos if c.get("words"))
    segmentos = sum(len(c.get("words") or ()) for c in novos)
    print("payload  : %s sha256=%s" % (fixture, sha))
    print("entrada  : %s schema=%s cues=%d" % (path, velho.get("schema"), len(antigos)))
    print("conferido: %d/%d cues iguais em start/end/text" % (len(novos), len(antigos)))
    print("revelacao: %d cues com relogio, %d palavras com instante" % (com_relogio, segmentos))
    if args.check:
        print("--check: nada escrito")
        return 0

    novo = dict(velho)
    novo["schema"] = yc.CACHE_SCHEMA
    novo["cues"] = novos
    novo["rebuilt_from"] = {"path": os.path.relpath(fixture, REPO).replace("\\", "/"),
                            "sha256": sha}
    novo["rebuilt_at"] = datetime.datetime.now().replace(microsecond=0).isoformat()
    novo["rebuilt_note"] = ("entrada de 2026-10-22 reconstruida a partir do payload capturado do "
                            "player para lhe acrescentar o relogio da revelacao (`words`); "
                            "fetched_at e o da recolha original")

    tmp = yc._cache_path(args.video) + ".tmp-rebuild.jsonl"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(novo, ensure_ascii=False) + "\n")
    os.replace(tmp, path)

    lido = yc._cache_read(args.video, allow_stale=True)
    ok = bool(lido) and len(lido.get("cues") or []) == len(novos)
    tem_relogio = bool(lido) and all((c.get("words") for c in (lido.get("cues") or [])))
    print("escrito  : %s" % path)
    print("releitura: cache_read aceita=%s cues=%d relogio_em_todos=%s stale=%s"
          % (ok, len((lido or {}).get("cues") or []), tem_relogio,
             (lido or {}).get("stale")))
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
