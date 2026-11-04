#!/usr/bin/env python
# NO-BUG: O CUE DO YOUTUBE CHEGA AO ECRA 1:1 -- o instrumento. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""O CUE DO YOUTUBE CHEGA AO ECRA 1:1 -- o instrumento.

O QUE MEDE, e porque e' este numero. O defeito observado (2026-11-03, instancia
viva pid 28888, `_main/webview-run.log`): 18 linhas
`YOUTUBE_CAPTION ... why=painted-other-track`, o cue a chegar INTEIRO de segundo a
segundo, e nos a pinta-lo inteiro no instante da chegada. A pergunta que fecha
isso nao e' "quantos ms o texto esperou na fila" -- essa ja' tem instrumento
(`CAPTION_OVERLAY_LAG`, do shell, em relogio de parede). E' esta:

    quando a NOSSA legenda pintou o cue, em que instante do VIDEO ela estava?

`land_lag_ms = (relogio do player na PRIMEIRA pintura) - (t0 do cue)`. Os dois
numeros estao em segundos de VIDEO, escritos pelo overlay na linha
`CAPTION_LAND` (ver `app/webview/caption_overlay.py::_log_land`):

    CAPTION_LAND cue_t0=350.694 paint_t=350.712 lag_ms=18 rows=2 words=3 text="..."

  * `cue_t0`  -- o `start` da cue que o shell mandou pintar;
  * `paint_t` -- o relogio do player no instante em que o `UpdateLayeredWindow`
                 devolveu OK (a extrapolacao do ancora do overlay, nao o
                 instante da chegada);
  * `lag_ms`  -- `paint_t - cue_t0`, em ms. O oraculo REFAZ a conta e recusa um
                 ficheiro onde os tres numeros nao concordam: um instrumento que
                 acredita no seu proprio campo resumido nao mede nada.

`cues_descartados` conta os cues que NUNCA chegaram ao ecra: `CAPTION_CUE_DROP`
(um cue novo substituiu-o antes de pintar) e `CAPTION_DROP_EPOCH` (o shell
descartou-o no slot por a fonte ter mudado). Um lag bom com metade dos cues
descartados nao e' uma legenda 1:1.

A SEGUNDA METADE DA ACEITACAO, no mesmo ficheiro porque e' a mesma linha do ecra:
`rows` > 2 numa pintura e' uma violacao (o dono pediu no maximo duas linhas).

CODIGOS DE SAIDA
  0  PASS  -- mediana <= 150 ms, >= 5 cues pintados, nenhuma pintura com > 2 linhas
  1  FAIL  -- mediana > 150 ms com >= 5 cues, OU uma pintura com > 2 linhas
  2  SEM DADOS -- nenhum `CAPTION_LAND`, menos de 5 cues (uma amostra de 4 nao e'
              uma medicao), ficheiro ilegivel, ou numeros que nao concordam

`--neg-arm` prova o instrumento contra si proprio: parte de um log sintetico
VERDE (construido em memoria, porque o processo que la' corre ainda nao tem a
linha nova), exige GREEN nele, e depois aplica mutantes que TEM de cair. Um
mutante que sobreviva e' um furo do oraculo, nao um resultado.

Uso:
  python _main/youtube-land-oracle.py
  python _main/youtube-land-oracle.py --log _main/webview-run.log
  python _main/youtube-land-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG = os.path.join(HERE, "webview-run.log")

#: O limiar da aceitacao, em ms. Acima disto a legenda entra depois do player.
LIMIAR_MS = 150
#: Abaixo disto nao ha' medicao: 4 cues nao fazem uma mediana que se possa citar.
MIN_CUES = 5
#: O tecto de linhas do ecra (`rcRows: 2` do payload do YouTube).
MAX_ROWS = 2

_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
_LAND = re.compile(
    r"CAPTION_LAND\s+cue_t0=(-?\d+(?:\.\d+)?)\s+"
    r"paint_t=(-?\d+(?:\.\d+)?)\s+"
    r"lag_ms=(-?\d+)(?:\s+rows=(\d+))?")
_DROP = re.compile(r"CAPTION_CUE_DROP\s+cue_t0=(-?\d+(?:\.\d+)?)\s+reason=(\S+)")
_EPOCH = re.compile(r"CAPTION_DROP_EPOCH\b")
_DECIDED = re.compile(
    r"YOUTUBE_CAPTION\s+video_id=\S+\s+cue=(-?\d+(?:\.\d+)?)\s+t=")


def parse(lines):
    """`(land, drops, epoch_drops, decided, n_lines)` de linhas de log."""
    land = []
    drops = []
    epoch_drops = 0
    decided = set()
    n_lines = 0
    for raw in lines:
        n_lines += 1
        line = raw.rstrip("\n")
        if "CAPTION_" not in line and "YOUTUBE_CAPTION" not in line:
            continue
        m = _LAND.search(line)
        if m:
            land.append({
                "cue_t0": float(m.group(1)),
                "paint_t": float(m.group(2)),
                "lag_ms": int(m.group(3)),
                "rows": int(m.group(4)) if m.group(4) is not None else None,
            })
            continue
        m = _DROP.search(line)
        if m:
            drops.append({"cue_t0": float(m.group(1)), "reason": m.group(2)})
            continue
        if _EPOCH.search(line):
            epoch_drops += 1
            continue
        m = _DECIDED.search(line)
        if m:
            decided.add(round(float(m.group(1)), 3))
    return land, drops, epoch_drops, decided, n_lines


def percentile(values, pct):
    """Posto mais proximo -- sem interpolacao, que num instrumento e' invencao."""
    if not values:
        return None
    ordered = sorted(values)
    k = max(1, int(round((float(pct) / 100.0) * len(ordered) + 0.4999)))
    return ordered[min(len(ordered) - 1, k - 1)]


def evaluate(land, drops, epoch_drops, decided):
    """O veredicto e os numeros que o sustentam.

    `rc` e' o contrato do ticket: 0 PASS, 1 FAIL, 2 SEM DADOS. `why` e' a razao
    escrita, para a proxima leitura nao ter de a deduzir.
    """
    out = {
        "pintados": 0,
        "descartados": len(drops) + int(epoch_drops),
        "decididos": len(decided),
        "mediana_ms": None,
        "p95_ms": None,
        "max_ms": None,
        "violacoes_linhas": [],
        "inconsistentes": [],
        "rc": 2,
        "why": "",
    }
    # DEDUPE POR `cue_t0`: o mesmo cue pintado duas vezes seria um segundo
    # `UpdateLayeredWindow` com o mesmo carimbo, ou seja um log mentiroso. Fica o
    # PRIMEIRO (o que o dono viu) e o segundo conta como inconsistencia.
    seen = {}
    for item in land:
        key = round(item["cue_t0"], 3)
        if key in seen:
            out["inconsistentes"].append(
                "cue_t0=%.3f pintado duas vezes" % key)
            continue
        seen[key] = item
        expect = int(round((item["paint_t"] - item["cue_t0"]) * 1000.0))
        if abs(expect - item["lag_ms"]) > 1:
            out["inconsistentes"].append(
                "cue_t0=%.3f lag_ms=%d mas paint_t-cue_t0=%d"
                % (key, item["lag_ms"], expect))
        if item.get("rows") is not None and item["rows"] > MAX_ROWS:
            out["violacoes_linhas"].append(
                "cue_t0=%.3f rows=%d" % (key, item["rows"]))
    items = [seen[key] for key in sorted(seen)]
    out["pintados"] = len(items)
    if not items:
        out["why"] = "nenhum CAPTION_LAND no log (a app viva ainda nao tem a linha)"
        return out
    lags = [int(round(it["lag_ms"])) for it in items]
    out["mediana_ms"] = percentile(lags, 50)
    out["p95_ms"] = percentile(lags, 95)
    out["max_ms"] = max(lags)
    if out["inconsistentes"]:
        out["why"] = ("numeros que nao concordam (%s)"
                      % out["inconsistentes"][0])
        return out
    if out["pintados"] < MIN_CUES:
        out["why"] = ("%d cue(s) pintado(s) < %d: amostra pequena demais para "
                      "uma mediana" % (out["pintados"], MIN_CUES))
        return out
    if out["violacoes_linhas"]:
        out["rc"] = 1
        out["why"] = ("pintura com mais de %d linhas (%s)"
                      % (MAX_ROWS, out["violacoes_linhas"][0]))
        return out
    if out["mediana_ms"] > LIMIAR_MS:
        out["rc"] = 1
        out["why"] = ("mediana %d ms > %d ms: o cue entra depois do player"
                      % (out["mediana_ms"], LIMIAR_MS))
        return out
    out["rc"] = 0
    out["why"] = "mediana %d ms <= %d ms em %d cues" % (
        out["mediana_ms"], LIMIAR_MS, out["pintados"])
    return out


def report(out, stream):
    stream.write("CUES      pintados=%d descartados=%d decididos=%d\n"
                 % (out["pintados"], out["descartados"], out["decididos"]))
    if out["pintados"]:
        stream.write("LAG       mediana=%sms p95=%sms max=%sms "
                     "(limiar %dms, minimo %d cues)\n"
                     % (out["mediana_ms"], out["p95_ms"], out["max_ms"],
                        LIMIAR_MS, MIN_CUES))
    if out["violacoes_linhas"]:
        stream.write("ROWS      %d pintura(s) acima de %d linhas: %s\n"
                     % (len(out["violacoes_linhas"]), MAX_ROWS,
                        ", ".join(out["violacoes_linhas"][:5])))
    for bad in out["inconsistentes"][:5]:
        stream.write("BAD       %s\n" % bad)
    word = ("PASS" if out["rc"] == 0 else
            "FAIL" if out["rc"] == 1 else "SEM DADOS")
    stream.write("VERDICT   %s -- %s\n" % (word, out["why"]))
    # AS DUAS FRASES QUE A BATERIA LE' (2026-11-03). Sem elas o passo nao podia ser
    # declarado skip-capable: `:skipped` exige rc=0 e uma das duas frases, e um
    # `SEM DADOS` que saia 2 seria contado FAIL -- mas nao ha' portao nenhum que
    # tenha falhado quando a sessao viva ainda nao escreveu `CAPTION_LAND`, e um
    # passo saltado NAO e' um portao que passou: conta-se SKIPPED, nunca verde.
    stream.write("YOUTUBE-LAND VERDICT: %s\n"
                 % ("PASS" if out["rc"] == 0 else
                    "FAIL" if out["rc"] == 1 else "SKIPPED"))


# ── O BRAÇO NEGATIVO ─────────────────────────────────────────────────────────
def _synthetic(green=True):
    """Um log sintetico no formato REAL das linhas (o processo vivo e' antigo).

    Construido em memoria para o braco negativo poder correr hoje: o instrumento
    tem de saber distinguir um log bom de um log mau antes de existir um log bom.
    """
    lines = []
    for i in range(8):
        t0 = 100.0 + i * 2.0
        lag = 12 + i if green else 420 + i
        lines.append(
            "2026-11-03 05:43:%02d.000 sotto: CAPTION_LAND cue_t0=%.3f "
            "paint_t=%.3f lag_ms=%d rows=2 words=3 text=\"linha %d\"\n"
            % (i, t0, t0 + lag / 1000.0, lag, i))
        lines.append(
            "2026-11-03 05:43:%02d.100 sotto: YOUTUBE_CAPTION video_id=abc "
            "cue=%.3f t=%.2f track=pt-orig text='linha %d' "
            "why=painted-other-track\n" % (i, t0, t0 + 0.01, i))
    lines.append("2026-11-03 05:43:09.000 sotto: CAPTION_CUE_DROP cue_t0=90.000 "
                 "reason=superseded\n")
    lines.append("2026-11-03 05:43:10.000 sotto: CAPTION_DROP_EPOCH enq=1 cur=2 "
                 "text=\"x\"\n")
    return lines


def _mutate(lines, kind):
    out = []
    for line in lines:
        if kind == "late":
            m = _LAND.search(line)
            if m:
                t0 = float(m.group(1))
                paint = float(m.group(2)) + 0.5
                lag = int(round((paint - t0) * 1000.0))
                line = ("2026-11-03 05:43:00.000 sotto: CAPTION_LAND "
                        "cue_t0=%.3f paint_t=%.3f lag_ms=%d rows=2 words=3 "
                        "text=\"atrasado\"\n" % (t0, paint, lag))
            out.append(line)
            continue
        if kind == "no-land":
            if _LAND.search(line):
                continue
            out.append(line)
            continue
        if kind == "one-cue":
            if not _LAND.search(line) and "CAPTION_LAND" in line:
                continue
            out.append(line)
            continue
        if kind == "lying-lag":
            m = _LAND.search(line)
            if m:
                line = ("2026-11-03 05:43:00.000 sotto: CAPTION_LAND "
                        "cue_t0=%s paint_t=%s lag_ms=5 rows=2 words=3 "
                        "text=\"mentira\"\n" % (m.group(1), m.group(2)))
            out.append(line)
            continue
        if kind == "no-t0":
            if _LAND.search(line):
                line = ("2026-11-03 05:43:00.000 sotto: CAPTION_LAND "
                        "paint_t=101.000 lag_ms=12 rows=2 words=3 text=\"x\"\n")
            out.append(line)
            continue
        if kind == "three-rows":
            if _LAND.search(line):
                line = line.replace("rows=2 ", "rows=3 ")
            out.append(line)
            continue
        out.append(line)
    if kind == "one-cue":
        kept = [x for x in out if _LAND.search(x)][0]
        out = [x for x in out if not _LAND.search(x)] + [kept]
    return out


def neg_arm():
    """Cada mutante TEM de cair; o log limpo TEM de passar."""
    print("NEG-ARM fixture  log sintetico VERDE")
    green = evaluate(*parse(_synthetic(True))[:4])
    report(green, sys.stdout)
    ok = green["rc"] == 0
    print("NEG-ARM control  rc=%d %s" % (green["rc"], "PASS" if ok else "** MUDO **"))
    mutants = [
        ("late", "pintura 500 ms atrasada", 1),
        ("no-land", "sem CAPTION_LAND nenhum", 2),
        ("one-cue", "um cue so' (amostra pequena)", 2),
        ("lying-lag", "lag_ms a mentir contra paint_t", 2),
        ("no-t0", "linha sem cue_t0 (nao se le')", 2),
        ("three-rows", "pintura com 3 linhas", 1),
    ]
    caught = 0
    for kind, why, want in mutants:
        out = evaluate(*parse(_mutate(_synthetic(True), kind))[:4])
        hit = out["rc"] == want
        caught += 1 if hit else 0
        print("NEG-ARM %-10s %-38s want rc=%d got rc=%d %s"
              % (kind, why, want, out["rc"], "CAIU" if hit else "** PASSOU **"))
    if os.path.exists(DEFAULT_LOG):
        # O LOG REAL, quando ja' tiver linhas: o mesmo mutante de atraso tem de
        # cair nele tambem. Um oraculo so' provado em fixture e' um oraculo de
        # fixture.
        with open(DEFAULT_LOG, encoding="utf-8", errors="replace") as fh:
            real = fh.readlines()
        parsed = parse(real)
        if parsed[0]:
            out = evaluate(*parse(_mutate(real, "late"))[:4])
            hit = out["rc"] == 1
            caught += 1 if hit else 0
            print("NEG-ARM %-10s %-38s want rc=1 got rc=%d %s"
                  % ("real-late", "log VIVO atrasado 500 ms", out["rc"],
                     "CAIU" if hit else "** PASSOU **"))
        else:
            print("NEG-ARM real       saltado: o log vivo ainda nao tem CAPTION_LAND")
    total = len(mutants) + (1 if _real_land_count() else 0)
    print("NEG-ARM %d of %d mutant(s) caught" % (caught, total))
    # CONTRATO DA BATERIA: rc=1 = o mutante foi apanhado; rc=0 = o controlo
    # NAO derrubou nada (o `:expectred` le isso como falha).
    if ok and caught == total:
        print("NEG-ARM: PASS")
        return 1
    print("NEG-ARM: FAIL")
    return 0


def _real_land_count():
    if not os.path.exists(DEFAULT_LOG):
        return 0
    with open(DEFAULT_LOG, encoding="utf-8", errors="replace") as fh:
        return sum(1 for line in fh if "CAPTION_LAND" in line)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=("Mede land_lag_ms por cue pintado (paint_t - cue_t0) no log "
                     "vivo: 0 PASS, 1 FAIL (mediana > %d ms com >= %d cues, ou "
                     "pintura com > %d linhas), 2 SEM DADOS."
                     % (LIMIAR_MS, MIN_CUES, MAX_ROWS)))
    ap.add_argument("--log", default=DEFAULT_LOG,
                    help="log a ler (por omissao %s)" % DEFAULT_LOG)
    ap.add_argument("--neg-arm", action="store_true",
                    help="prova o oraculo contra mutantes: todos TEM de cair")
    ap.add_argument("--tail", type=int, default=0,
                    help="ler so' as ultimas N linhas (0 = ficheiro inteiro)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if args.neg_arm:
        return neg_arm()
    try:
        with open(args.log, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print("SEM DADOS -- log ilegivel: %r" % (exc,))
        print("YOUTUBE-LAND VERDICT: SKIPPED")
        return 0
    if args.tail and args.tail > 0:
        lines = lines[-args.tail:]
    land, drops, epoch_drops, decided, n_lines = parse(lines)
    print("LOG       %s (%d linhas, %d CAPTION_LAND)"
          % (args.log, n_lines, len(land)))
    out = evaluate(land, drops, epoch_drops, decided)
    report(out, sys.stdout)
    # SEM DADOS (rc=2 do ticket) e' rc=0 NA BATERIA, com a frase de skip: e' a
    # unica forma de o passo poder ser skip-capable sem transformar um skip num
    # FAIL nem um skip num verde.
    return 0 if out["rc"] == 2 else out["rc"]


if __name__ == "__main__":
    sys.exit(main())
