#!/usr/bin/env python
"""YOUTUBE DRIFT -- o RELOGIO de cada linha do player contra o relogio do payload.

A pergunta deste oraculo e uma so: quando o player do YouTube mostra uma linha na tela,
quantos MILISSEGUNDOS antes/depois do instante que o payload do proprio player declara?

  referencia    = payload do player (`yt-<video>.en-orig.json3`):
                  o inicio de cada linha e `tStartMs` + o `tOffsetMs` do segmento que
                  contem a ultima palavra visivel da linha observada.
  observacao    = o player ao vivo (`yt-<video>.live-compare-<data>.json`):
                  `samples[].t` e o relogio, `samples[].segs[].t` e o texto da linha
                  visivel nesse instante; a primeira amostra em que a linha aparece e a
                  observacao dessa linha.
  drift_ms      = observado_ms - referencia_ms   (sinal, nunca booleano)

Nao ha "sincronizado" neste ficheiro: um numero por linha, com sinal. Uma linha que nao
tem referencia no payload sai como `drift_ms=NA` com a razao, nunca e saltada em silencio.

Arm negativa (`--neg-arm`): desloca a REFERENCIA do payload em +250 ms (offset declarado)
e exige que a medicao veja exactamente esse deslocamento; falha de proposito (rc=1) para
provar que o instrumento detecta o desvio que devia detectar.
"""
# NO-BUG: check do objectivo do dono de 2026-10-26 -- o tempo da legenda do YouTube medido
# em drift_ms por linha, com arm negativa que desloca a referencia e tem de a ver.
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

VIDEO = "WdaHAGRBB6s"
FIXTURE = os.path.join(HERE, "fixtures", "yt-%s.en-orig.json3" % VIDEO)
LIVE = os.path.join(HERE, "fixtures", "yt-%s.live-compare-20261026.json" % VIDEO)

#: O desvio que a arm negativa injeta na referencia. Fixo e declarado no output.
NEG_OFFSET_MS = 250.0

#: Aspas tipograficas que o player pode usar e o payload nao (para o match de texto).
_QUOTES = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-",
}


# ----------------------------------------------------------------- normalizacao


def norm_token(tok):
    """Chave de comparacao: NFKC, aspas tipograficas, caixa. Espaco nao entra aqui."""
    s = unicodedata.normalize("NFKC", str(tok or ""))
    for a, b in _QUOTES.items():
        s = s.replace(a, b)
    return s.casefold()


def split_words(text):
    """Palavras de um texto, ja sem o marcador de falante `>>` (payload E player)."""
    words = [w for w in str(text or "").split() if w]
    if words and words[0] == ">>":
        words.pop(0)
    elif words and words[0].startswith(">>"):
        words[0] = words[0][2:]
        if not words[0]:
            words.pop(0)
    return words


def round_ms(x):
    """Inteiro mais proximo, meio para longe do zero (nao bancario)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def signed(n):
    return "%+d" % n


# ----------------------------------------------------------------- as duas pontas


def load_json(path):
    """Le um fixture; devolve (doc, None) ou (None, erro legivel)."""
    if not os.path.isfile(path):
        return None, "fixture ausente: %s" % path
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except Exception as exc:  # noqa: BLE001 -- fixture corrompido e infra, nao medicao
        return None, "fixture ilegivel: %s (%s)" % (path, exc)


def payload_rows(doc, offset_ms=0.0):
    """As LINHAS do payload: cada evento de texto, com o relogio de cada palavra.

    Os eventos `aAppend` cujo texto e so `\\n` sao SEPARADORES de linha, nao linhas.
    `offset_ms` desloca a referencia inteira (usado pela arm negativa).
    """
    rows = []
    for ev in doc.get("events") or ():
        segs = ev.get("segs") or ()
        if not segs:
            continue
        plain = " ".join((sg.get("utf8") or "") for sg in segs).split()
        if not plain or set(plain) <= {"\n"}:
            continue
        t0 = ev.get("tStartMs")
        words = []
        for sg in segs:
            text = sg.get("utf8") or ""
            if t0 is None:
                ts = None
            else:
                ts = float(t0) + float(sg.get("tOffsetMs") or 0.0) + float(offset_ms)
            for tok in split_words(text):
                words.append((tok, ts))
        if not words:
            continue
        rows.append({
            "cue": len(rows) + 1,
            "t0_ms": None if t0 is None else float(t0) + float(offset_ms),
            "words": words,
            "key": tuple(norm_token(w) for w, _ts in words),
            "text": " ".join(w for w, _ts in words),
        })
    return rows


def player_rows(doc):
    """As LINHAS visiveis do player, com o instante da PRIMEIRA amostra em que aparecem.

    Texto igual em amostras diferentes e a MESMA linha a ser redesenhada: guarda-se a
    primeira vez. `v: false` (linha a desvanecer) nao conta como visivel.
    """
    seen = {}
    order = []
    for sample in doc.get("samples") or ():
        at_ms = float(sample.get("t") or 0.0) * 1000.0
        for seg in sample.get("segs") or ():
            if seg.get("v") is False:
                continue
            words = split_words(seg.get("t"))
            if not words:
                continue
            key = tuple(norm_token(w) for w in words)
            if key in seen:
                continue
            seen[key] = {"at_ms": at_ms, "words": words,
                         "key": key, "text": " ".join(words)}
            order.append(key)
    return [seen[k] for k in order]


def match(row, rows):
    """A linha do payload de que `row` e prefixo de palavras. Devolve (linha, n_candidatas)."""
    cands = []
    n = len(row["key"])
    for cand in rows:
        if len(cand["key"]) >= n and cand["key"][:n] == row["key"]:
            cands.append(cand)
    if not cands:
        return None, 0
    if len(cands) > 1:
        cands.sort(key=lambda c: (abs((c["words"][n - 1][1] or 0.0) - row["at_ms"]), c["cue"]))
    return cands[0], len(cands)


# ----------------------------------------------------------------- a medicao


def measure(payload, live, offset_ms=0.0):
    """Uma medicao completa. Cada item: cue, texto, drift_ms (ou None) e a razao."""
    rows = payload_rows(payload, offset_ms=offset_ms)
    if not rows:
        return None, "payload sem linhas de legenda (events com segs vazios)"
    observed = player_rows(live)
    if not observed:
        return None, "fixture do player sem nenhuma linha visivel (samples[].segs[].v)"

    out = []
    for row in observed:
        cand, n_cands = match(row, rows)
        item = {"row": row, "cue": None, "ref_ms": None,
                "drift_ms": None, "reason": None, "candidates": n_cands}
        if cand is None:
            item["reason"] = "nenhuma linha do payload comeca por estas palavras"
        else:
            item["cue"] = cand["cue"]
            ref = cand["words"][len(row["key"]) - 1][1]
            item["ref_ms"] = ref
            if ref is None:
                item["reason"] = "evento do payload sem tStartMs (sem referencia)"
            else:
                item["drift_ms"] = row["at_ms"] - ref
        out.append(item)
    return {"rows": out, "payload_rows": rows, "observed_rows": observed,
            "samples": len(live.get("samples") or ())}, None


def summary(drifts):
    if not drifts:
        return None
    return {
        "count": len(drifts),
        "min": min(drifts),
        "max": max(drifts),
        "mean": statistics.fmean(drifts),
        "median": statistics.median(drifts),
    }


def sample_gaps(doc):
    ts = [float(s.get("t") or 0.0) * 1000.0 for s in (doc.get("samples") or ())]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    return gaps


# ----------------------------------------------------------------- relatorio


def fmt_row(item):
    row = item["row"]
    drift = item["drift_ms"]
    head = "cue=%s row=%s drift_ms=%s" % (
        item["cue"] if item["cue"] is not None else "NA",
        row["text"],
        "NA" if drift is None else signed(round_ms(drift)))
    if drift is None:
        head += " reason=%s" % item["reason"]
    else:
        head += " observed_ms=%.1f ref_ms=%.1f" % (row["at_ms"], item["ref_ms"])
    if item["candidates"] > 1:
        head += " candidates=%d" % item["candidates"]
    return head


def report(m, payload_path, live_path, payload_sha, live_sha, gaps, label):
    rows = m["rows"]
    drifts = [r["drift_ms"] for r in rows if r["drift_ms"] is not None]
    unmatched = [r for r in rows if r["drift_ms"] is None]
    matched_payload = sorted({r["cue"] for r in rows if r["cue"] is not None})

    out = ["video            : %s" % VIDEO,
           "REFERENCIA       : payload do player -- %s (sha256 %s)" % (payload_path, payload_sha),
           "OBSERVACAO       : player ao vivo      -- %s (sha256 %s)" % (live_path, live_sha),
           "regra            : drift_ms = observado_ms - referencia_ms",
           "referencia       : tStartMs da linha + tOffsetMs do segmento da ultima palavra observada",
           "observacao       : samples[].t da PRIMEIRA amostra em que a linha aparece visivel",
           "sinal            : drift_ms < 0 => o player mostrou ANTES do payload => a NOSSA",
           "                   revelacao (que segue o payload) esta TARDE por |drift_ms|;",
           "                   drift_ms > 0 => a nossa revelacao esta CEDO por drift_ms.",
           "texto            : espaco normalizado e marcador de falante `>>` removido nos DOIS lados",
           "amostras         : %d | passo min/mediana/max = %.0f/%.0f/%.0f ms (resolucao da medicao)"
           % (m["samples"],
              min(gaps) if gaps else 0.0,
              statistics.median(gaps) if gaps else 0.0,
              max(gaps) if gaps else 0.0),
           "linhas do payload: %d | observadas: %d | com drift: %d | NA: %d"
           % (len(m["payload_rows"]), len(rows), len(drifts), len(unmatched)),
           ""]
    if label:
        out.append("MODO             : %s" % label)
        out.append("")
    out.append("linhas medidas (ordem de observacao):")
    for item in rows:
        out.append("  " + fmt_row(item))

    s = summary(drifts)
    out.append("")
    if s is None:
        out.append("SUMMARY medicao vazia: nenhuma linha do player casou com o payload (rc=2)")
    else:
        out.append("SUMMARY n=%d min_ms=%s max_ms=%s mean_ms=%s median_ms=%s"
                   % (s["count"], signed(round_ms(s["min"])), signed(round_ms(s["max"])),
                      "%+.1f" % s["mean"], "%+.1f" % s["median"]))
        never = [r["cue"] for r in m["payload_rows"] if r["cue"] not in matched_payload]
        out.append("payload nunca observado: %d/%d linhas (fora da janela das amostras)%s"
                   % (len(never), len(m["payload_rows"]),
                      (": cues " + ",".join(str(c) for c in never)) if never else ""))
        out.append("CONVENCAO drift_ms negativo = player adiantado = a nossa revelacao TARDE")
    return "\n".join(out), s, unmatched


# ----------------------------------------------------------------- main


def sha256_of(path):
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="YouTube drift: tempo de cada linha do player contra o payload, em ms")
    ap.add_argument("--fixture", default=FIXTURE, help="payload do player (.json3)")
    ap.add_argument("--live", default=LIVE, help="amostras do player (.json)")
    ap.add_argument("--neg-arm", action="store_true",
                    help="desloca a referencia em +%d ms e FALHA (rc=1) por desenho"
                         % int(NEG_OFFSET_MS))
    ap.add_argument("--neg-offset-ms", type=float, default=NEG_OFFSET_MS,
                    help="desvio injectado pela --neg-arm (default %d)" % int(NEG_OFFSET_MS))
    ap.add_argument("--write", default=None, help="escrever o relatorio neste ficheiro")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 -- consola antiga: nao e falha da medicao
        pass

    payload, err = load_json(args.fixture)
    if err:
        print("MEDICAO AUSENTE: %s" % err)
        print("YOUTUBE-DRIFT VERDICT NO-MEASURE (rc=2) -- ausencia de fixture nao e medicao")
        return 2
    live, err = load_json(args.live)
    if err:
        print("MEDICAO AUSENTE: %s" % err)
        print("YOUTUBE-DRIFT VERDICT NO-MEASURE (rc=2) -- ausencia de fixture nao e medicao")
        return 2

    m, err = measure(payload, live)
    if err:
        print("MEDICAO AUSENTE: %s" % err)
        print("YOUTUBE-DRIFT VERDICT NO-MEASURE (rc=2) -- payload/player sem linhas")
        return 2

    gaps = sample_gaps(live)
    text, s, _unmatched = report(m, args.fixture, args.live,
                                 sha256_of(args.fixture), sha256_of(args.live),
                                 gaps, "referencia do payload, sem desvio")
    if s is None:
        print(text)
        print("YOUTUBE-DRIFT VERDICT NO-MEASURE (rc=2) -- nenhuma linha com drift")
        return 2

    # ------------------------------------------------------------- arm negativa
    if not args.neg_arm:
        print(text)
        print("")
        print("YOUTUBE-DRIFT VERDICT MEASURED (rc=0) -- n=%d mean_ms=%+.1f median_ms=%+.1f"
              % (s["count"], s["mean"], s["median"]))
        if args.write:
            with open(args.write, "w", encoding="utf-8", newline="") as fh:
                fh.write(text + "\n")
        return 0

    off = float(args.neg_offset_ms)
    shifted, err = measure(payload, live, offset_ms=off)
    if err:
        print("NEG-ARM FAIL: medicao deslocada impossivel: %s" % err)
        return 3
    text2, s2, _u2 = report(shifted, args.fixture, args.live,
                            sha256_of(args.fixture), sha256_of(args.live),
                            gaps, "ARM NEGATIVA: referencia do payload deslocada em %+d ms"
                                  % int(off))
    print(text2)

    pos = {(r["cue"], r["row"]["text"]): r["drift_ms"] for r in m["rows"] if r["drift_ms"] is not None}
    neg = {(r["cue"], r["row"]["text"]): r["drift_ms"] for r in shifted["rows"] if r["drift_ms"] is not None}
    common = sorted(set(pos) & set(neg))
    blind = [k for k in common if abs((neg[k] - pos[k]) + off) > 1e-6]
    missing = sorted(set(pos) ^ set(neg))

    print("")
    print("NEG-ARM: desvio injectado na referencia = %+d ms (payload tStartMs/tOffsetMs)" % int(off))
    print("NEG-ARM: linhas comparadas nas duas medicoes = %d | sem par = %d"
          % (len(common), len(missing)))
    if s2 is not None and s is not None:
        print("NEG-ARM: mean_ms %+.1f -> %+.1f (delta %+.1f ms, esperado %+.1f)"
              % (s["mean"], s2["mean"], s2["mean"] - s["mean"], -off))
    for key in common[:3]:
        print("NEG-ARM: %s | sem desvio drift_ms=%s | com desvio drift_ms=%s (delta %+d)"
              % (key[1], signed(round_ms(pos[key])), signed(round_ms(neg[key])),
                 round_ms(neg[key] - pos[key])))
    if blind or missing:
        for key in blind[:5]:
            print("NEG-ARM: CIEGO em %s (delta %+d, esperado %+d)"
                  % (key[1], round_ms(neg[key] - pos[key]), int(-off)))
        print("NEG-ARM FAIL: o instrumento nao viu o desvio injectado de %+d ms" % int(off))
        return 3
    print("NEG-ARM PASS: o instrumento viu o desvio injectado de %+d ms em %d/%d linhas "
          "(cada drift_ms baixou exactamente %+d ms)" % (int(off), len(common), len(common), int(-off)))
    print("YOUTUBE-DRIFT VERDICT RED-BY-DESIGN (rc=1) -- a referencia foi deslocada em %+d ms "
          "e a medicao tem de falhar" % int(off))
    if args.write:
        with open(args.write, "w", encoding="utf-8", newline="") as fh:
            fh.write(text2 + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
