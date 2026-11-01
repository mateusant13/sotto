#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: ratchet de proveniencia das afirmacoes numericas do AGENTS.md; nao desbloqueia um bug nomeado, impede que um numero sem instrumento volte a ser lei
"""CLAIMS-DATE ORACLE -- nenhuma afirmacao numerica no `AGENTS.md` sem data e instrumento.

A LEI (roadmap de observabilidade, P0.3, 2026-10-23): *"uma afirmacao numerica no
`AGENTS.md` sem data/medicao ao lado e vermelha; baseline ratchet"*. A razao esta na lei 1
do `docs/quality-protocol.md`: *"um numero derivado publica-se **com populacao e janela**"*,
e o `AGENTS.md` e o ficheiro que **todos** os agentes leem -- um numero sem prova ali e lido
como facto por cada lane que passa.

A UNIDADE DA AFIRMACAO E O BLOCO, NAO A LINHA. Medido 2026-10-25 na primeira versao deste
portao: a leitura linha-a-linha acusava 23 sitios, e quase todos eram a **continuacao** de
uma frase cuja cabeca (no mesmo paragrafo) carrega a data -- `re-measured 2026-10-24 06:5x`
na linha de cima, os numeros na de baixo. Um bloco e a corrida de linhas nao vazias que
contem a afirmacao; a data pode estar em qualquer linha dele. Fechados os blocos, restam
**7** afirmacoes sem data -- e essas sao divida real, congelada no baseline.

O QUE CONTA COMO AFIRMACAO. Uma linha que traga um numero com **unidade de medida** (B,
bytes, KB, MB, GB, TB, lines, linhas, CRLF, ms, min, passos, processos, threads), um
numero com `%`, ou um digest de 64 hex. Um numero sem unidade ("4 guardas") nao e uma
medicao e nao e julgado aqui. Linhas dentro de um bloco de codigo (```) sao PAYLOAD, nao
prosa, e ficam de fora.

A DATA. `20\d\d-\d\d-\d\d` ou a forma compacta `20\d{6}` que os nomes de ficheiro deste
repo usam (`docs/AGENTS-archive-20261021.md`). Nada de "recentemente": uma data e um
instante, e um instante e o que se pode reconferir.

O RATCHET, e as quatro maneiras de o furar que sao um check cada:

  1. new-undated-claim  surgiu uma afirmacao sem data que o baseline nao cobre -> RED
  2. baseline-schema    uma entrada sem `reason`/`date`/`instrument` (a data sem
                        instrumento e a mesma doenca numa tabela) -> RED
  3. baseline-ceiling   o baseline cresceu acima do `CEILING` pinado NESTE ficheiro (o
                        JSON nao pode levantar o seu proprio tecto) -> RED
  4. baseline-orphans   uma entrada aponta para bytes que ja nao sao uma afirmacao sem
                        data -- a licenca tem de ENCOLHER quando a linha e curada -> RED

O baseline e `_main/claims-date-baseline.json`. `--write-baseline` regenera-o, e recusa-se
a gravar mais de `CEILING` entradas: um regenerador que pode crescer e a amnistia que este
portao existe para nao ser.

    python _main\\claims-date-oracle.py             # rc=0 verde, rc=1 vermelho
    python _main\\claims-date-oracle.py --neg-arm   # rc=1 POR DESENHO
    python _main\\claims-date-oracle.py --write-baseline

Sem `subprocess`, sem rede, sem escrita dentro da raiz do repo (excepto `--write-baseline`,
que so toca no baseline). Nao lanca nada: le bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)

DOC_REL = "AGENTS.md"
BASELINE_REL = os.path.join("_main", "claims-date-baseline.json")

# O tecto da divida, pinado em CODIGO. Se descer, alguem curou afirmacoes; se subir, e uma
# decisao com recibo, nao um efeito secundario de regenerar o JSON.
# 7 -> 4 em 2026-10-25: as tres curadas foram `11 passos` x2 (contados no docs/bug-hunt.md) e
# `119 linhas de medicoes` (era 120 medido -- o numero estava VELHO, e a cura foi corrigi-lo).
CEILING = 3
#: Era 4 ate 2026-10-30. A entrada do 4-ter saiu do baseline porque o bloco dela
#: passou a ter data: uma licenca para uma afirmacao JA datada e uma licenca a mais,
#: e o ratchet deste portao so pode ENCOLHER.

DATE_RE = re.compile(r"20\d\d-\d\d-\d\d|20\d{6}")
DIGEST_RE = re.compile(r"\b[0-9A-Fa-f]{64}\b")
CLAIM_PATTERNS = (
    re.compile(r"\d[\d .,]*\s?(?:bytes|B|KB|MB|GB|TB|linhas|lines|CRLF|min|ms|passos|"
               r"processos|threads)\b"),
    re.compile(r"\d[\d .,]*\s?%"),
)
SCHEMA = "sotto-claims-date-baseline/1"
REQUIRED_FIELDS = ("line_sha256", "excerpt", "reason", "date", "instrument")
COPY_FILES = (DOC_REL, BASELINE_REL, os.path.join("_main", "claims-date-oracle.py"))
FENCE = "```"


def _read(root, rel):
    with open(os.path.join(root, rel), "rb") as fh:
        return fh.read().decode("utf-8", "replace")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_claim(line):
    return bool(DIGEST_RE.search(line)) or any(p.search(line) for p in CLAIM_PATTERNS)


def doc_lines(root):
    """As linhas do doc, com os blocos de codigo marcados como payload."""
    text = _read(root, DOC_REL)
    out = []
    in_fence = False
    for raw in text.splitlines():
        if raw.strip().startswith(FENCE):
            in_fence = not in_fence
            out.append((raw, True))
            continue
        out.append((raw, in_fence))
    return out


def blocks(lines):
    """Indices do bloco (corrida de linhas nao vazias) que contem cada indice."""
    owners = {}
    lo = None
    for index, (raw, payload) in enumerate(lines):
        if payload or not raw.strip():
            lo = None
            continue
        if lo is None:
            lo = index
        owners[index] = lo
    return owners


def violating(root):
    """[(line_sha256, excerpt)] -- afirmacoes numericas cujo bloco nao tem data."""
    lines = doc_lines(root)
    owners = blocks(lines)
    out = []
    for index, (raw, payload) in enumerate(lines):
        if payload or index not in owners or not is_claim(raw):
            continue
        head = owners[index]
        end = index
        while end + 1 < len(lines) and not lines[end + 1][1] and lines[end + 1][0].strip():
            end += 1
        window = "\n".join(lines[j][0] for j in range(head, end + 1))
        if DATE_RE.search(window):
            continue
        out.append((_sha(raw), raw.strip()))
    return out


def load_baseline(root):
    path = os.path.join(root, BASELINE_REL)
    with open(path, "rb") as fh:
        data = json.loads(fh.read().decode("utf-8", "replace"))
    return data


# ----------------------------------------------------------------------- checks


def check_new_undated(root, entries_by_hash, live):
    new = [exc for h, exc in live if h not in entries_by_hash]
    if new:
        detail = " | ".join(exc[:70] for exc in new[:4])
        return False, "%d afirmacao(oes) sem data fora do baseline: %s" % (len(new), detail)
    return True, "%d afirmacao(oes) sem data, todas com licenca no baseline" % len(live)


def check_baseline_schema(entries):
    problems = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append("entrada %d nao e um objecto" % position)
            continue
        for field in REQUIRED_FIELDS:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append("entrada %d sem %s" % (position, field))
        digest = entry.get("line_sha256")
        if isinstance(digest, str) and not re.fullmatch(r"[0-9a-f]{64}", digest):
            problems.append("entrada %d: line_sha256 nao e 64 hex minusculo" % position)
        stamp = entry.get("date")
        if isinstance(stamp, str) and stamp.strip() and not DATE_RE.fullmatch(stamp.strip()):
            problems.append("entrada %d: date %r nao e uma data" % (position, stamp))
    if problems:
        return False, "; ".join(problems[:4])
    return True, "%d entrada(s) com line_sha256/excerpt/reason/date/instrument" % len(entries)


def check_baseline_ceiling(data, entries):
    declared = data.get("ceiling")
    if declared != CEILING:
        return False, "o JSON declara ceiling=%r e este ficheiro pina %d: o tecto vem do " \
                      "codigo, nao do JSON" % (declared, CEILING)
    if len(entries) > CEILING:
        return False, "baseline com %d entradas > CEILING %d (a divida so pode encolher)" % (
            len(entries), CEILING)
    return True, "baseline com %d entrada(s) <= CEILING %d" % (len(entries), CEILING)


def check_baseline_orphans(entries_by_hash, live):
    live_hashes = {h for h, _ in live}
    orphans = [h for h in entries_by_hash if h not in live_hashes]
    if orphans:
        return False, "%d entrada(s) apontam para bytes que ja nao sao uma afirmacao sem " \
                      "data: a licenca tem de encolher" % len(orphans)
    return True, "nenhuma entrada orfa"


def run_checks(root):
    try:
        live = violating(root)
    except OSError as exc:
        return None, "AGENTS.md ilegivel: %s" % exc
    try:
        data = load_baseline(root)
    except (OSError, ValueError) as exc:
        # Um baseline em falta NAO e um no-verdict: e o caso em que TODAS as afirmacoes
        # estao fora de licenca. O fail-safe tem de ser vermelho, e o check di-lo.
        data = {"entries": [], "ceiling": CEILING, "_unreadable": str(exc)}
    entries = data.get("entries") or []
    by_hash = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("line_sha256"), str):
            by_hash[entry["line_sha256"]] = entry
    results = [
        ("new-undated-claim",) + check_new_undated(root, by_hash, live),
        ("baseline-schema",) + check_baseline_schema(entries),
        ("baseline-ceiling",) + check_baseline_ceiling(data, entries),
        ("baseline-orphans",) + check_baseline_orphans(by_hash, live),
    ]
    if data.get("_unreadable"):
        results = [("baseline-readable", False, "baseline ilegivel: %s" % data["_unreadable"])] + results
    return results, None


# --------------------------------------------------------------- bracos negativos


def _read_raw(root, rel):
    with open(os.path.join(root, rel), "rb") as fh:
        return fh.read()


def mut_append_undated_claim(root):
    body = _read_raw(root, DOC_REL)
    extra = "\nO worker em repouso consome 512 MB de RSS neste host.\n"
    with open(os.path.join(root, DOC_REL), "wb") as fh:
        fh.write(body + extra.encode("utf-8"))


def _mutate_baseline(root, mutate):
    path = os.path.join(root, BASELINE_REL)
    with open(path, "rb") as fh:
        data = json.loads(fh.read().decode("utf-8", "replace"))
    mutate(data)
    with open(path, "wb") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))


def mut_drop_entry_date(root):
    def mutate(data):
        for entry in data.get("entries") or []:
            if isinstance(entry, dict) and entry.get("date"):
                entry["date"] = ""
                return
        raise RuntimeError("nenhuma entrada com date para mutar")
    _mutate_baseline(root, mutate)


def mut_drop_entry_instrument(root):
    def mutate(data):
        for entry in data.get("entries") or []:
            if isinstance(entry, dict) and entry.get("instrument"):
                entry["instrument"] = ""
                return
        raise RuntimeError("nenhuma entrada com instrument para mutar")
    _mutate_baseline(root, mutate)


def mut_grow_baseline(root):
    def mutate(data):
        entries = data.get("entries") or []
        if not entries:
            raise RuntimeError("baseline vazio: nada para duplicar")
        clone = dict(entries[0])
        clone["line_sha256"] = _sha("licenca inventada para silenciar uma afirmacao nova")
        entries.append(clone)
        data["entries"] = entries
    _mutate_baseline(root, mutate)


def mut_orphan_entry(root):
    def mutate(data):
        entries = data.get("entries") or []
        if not entries:
            raise RuntimeError("baseline vazio: nada para orfanar")
        entries[0]["line_sha256"] = _sha("uma linha que ja nao existe no AGENTS.md")
        data["entries"] = entries
    _mutate_baseline(root, mutate)


def mut_drop_baseline(root):
    os.unlink(os.path.join(root, BASELINE_REL))


MUTATIONS = (
    ("append-undated-claim", mut_append_undated_claim, "new-undated-claim"),
    ("drop-entry-date", mut_drop_entry_date, "baseline-schema"),
    ("drop-entry-instrument", mut_drop_entry_instrument, "baseline-schema"),
    ("grow-baseline", mut_grow_baseline, "baseline-ceiling"),
    ("orphan-entry", mut_orphan_entry, "baseline-orphans"),
    ("drop-baseline", mut_drop_baseline, "new-undated-claim"),
)


def _tmp_base():
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return base if os.path.isdir(base) else tempfile.gettempdir()


def run_mutation(root, entry):
    name, mutate, expected = entry
    tmp = tempfile.mkdtemp(prefix="claims-date-", dir=_tmp_base())
    try:
        if os.path.realpath(tmp).startswith(os.path.realpath(root) + os.sep):
            raise RuntimeError("directorio temporario dentro da raiz do repo")
        for rel in COPY_FILES:
            target = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(target) or tmp, exist_ok=True)
            shutil.copyfile(os.path.join(root, rel), target)
        baseline, error = run_checks(tmp)
        if error is not None:
            return "COPY-BROKEN", [], error, expected
        broken = [n for n, ok, _ in baseline if not ok]
        if broken:
            return "COPY-BROKEN", baseline, "a copia intacta ja falha: %s" % ", ".join(broken), expected
        mutate(tmp)
        mutated, error = run_checks(tmp)
        if error is not None:
            return "NEG-ARM PASS", [("unreadable-after-mutation", False, error)], \
                   "o doc ficou ilegivel: %s" % error, expected
        refused = [n for n, ok, _ in mutated if not ok]
        if expected not in refused:
            return "NEG-ARM FAIL", mutated, \
                   "o check NOMEADO (%s) nao recusou; recusaram: %s" % (
                       expected, ", ".join(refused) or "nenhum"), expected
        return "NEG-ARM PASS", mutated, "recusou por: %s" % ", ".join(refused), expected
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# -------------------------------------------------------------------- baseline


def write_baseline(root):
    live = violating(root)
    if len(live) > CEILING:
        print("RED  %d afirmacao(oes) sem data > CEILING %d: nao se grava um baseline que "
              "cresce" % (len(live), CEILING))
        return 1
    try:
        existing = {e.get("line_sha256"): e for e in load_baseline(root).get("entries") or []
                    if isinstance(e, dict)}
    except (OSError, ValueError):
        existing = {}
    entries = []
    for digest, excerpt in live:
        prior = existing.get(digest) or {}
        entries.append({
            "line_sha256": digest,
            "excerpt": excerpt,
            "reason": prior.get("reason") or "REASON-MISSING preencher a mao",
            "date": prior.get("date") or "",
            "instrument": prior.get("instrument") or "",
        })
    payload = {
        "schema": SCHEMA,
        "why": "As afirmacoes numericas do AGENTS.md que ja existiam em 2026-10-23 sem data "
               "no bloco. Ratchet: so pode encolher. Ver _main/claims-date-oracle.py.",
        "ceiling": CEILING,
        "entries": entries,
    }
    with open(os.path.join(root, BASELINE_REL), "wb") as fh:
        fh.write(json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")
    print("wrote %s with %d entry(ies) (ceiling %d)" % (BASELINE_REL, len(entries), CEILING))
    return 0


# ------------------------------------------------------------------------- CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description="proveniencia das afirmacoes numericas do AGENTS.md")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--mutation", choices=[m[0] for m in MUTATIONS])
    parser.add_argument("--all-mutations", action="store_true")
    parser.add_argument("--neg-arm", action="store_true", help="corre TODOS os mutantes; rc=1 POR DESENHO")
    parser.add_argument("--list-mutations", action="store_true")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    if args.list_mutations:
        for name, _, expected in MUTATIONS:
            print("%s -> %s" % (name, expected))
        return 0

    root = os.path.abspath(args.root)
    if not os.path.isfile(os.path.join(root, DOC_REL)):
        print("CLAIMS-DATE: NO-VERDICT raiz sem %s" % DOC_REL)
        return 2

    if args.write_baseline:
        return write_baseline(root)

    selected = [m for m in MUTATIONS if args.mutation == m[0]]
    if args.all_mutations or args.neg_arm:
        selected = list(MUTATIONS)

    if not selected:
        results, error = run_checks(root)
        if error is not None:
            print("CLAIMS-DATE: NO-VERDICT %s" % error)
            return 2
        for name, ok, detail in results:
            print("CHECK %-20s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
        fail = sum(1 for _, ok, _ in results if not ok)
        verdict = "PASS" if fail == 0 else "FAIL"
        print("BATTERY-VERDICT claims-date %s checks=%d fail=%d" % (verdict, len(results), fail))
        return 0 if fail == 0 else 1

    outcomes = []
    for entry in selected:
        try:
            status, results, detail, expected = run_mutation(root, entry)
        except (OSError, RuntimeError, ValueError) as exc:
            print("MUTATION %-24s ERROR  %s" % (entry[0], exc))
            return 2
        print("MUTATION %-24s %s  [esperado: %s] %s" % (entry[0], status, expected, detail))
        for name, ok, check_detail in results:
            print("  mut-check %-20s %s  %s" % (name, "PASS" if ok else "FAIL", check_detail))
        outcomes.append(status)

    if "COPY-BROKEN" in outcomes:
        print("BATTERY-VERDICT claims-date NO-VERDICT copy-broken mutations=%d" % len(outcomes))
        return 2
    failed = sum(1 for status in outcomes if status != "NEG-ARM PASS")
    print("NEG-ARM %s mutations=%d named-arm-fail=%d"
          % ("PASS" if failed == 0 else "FAIL", len(outcomes), failed))
    return 1


if __name__ == "__main__":
    sys.exit(main())
