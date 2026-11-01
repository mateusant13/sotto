#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: P3.2 do roadmap de observabilidade (capacidade): duas listas do mesmo dono sobre a mesma coisa davam veredictos opostos e nada as juntava; o portao torna a contradicao impossivel de nao ver, sem a dar por resolvida
"""COMPLAINTS RECONCILE GATE -- uma linha por reclamacao, e o contraditorio deixa de ser silencioso.

O DEFEITO. `runs/TC-20261022-sotto-backlog.md` conta **39 linhas: 22 FECHADO, 6 PARCIAL, 10 ABERTO,
1 DECIDIDO**. `.opencode/complaints-closure.md` conta **31 seccoes, 31 fechadas, 81/81 reclamacoes
cobertas**, e entre as fontes das suas seccoes estao as mesmas mensagens do dono que o backlog diz
ABERTAS (`L100` -> R16/R18, `L121` -> R15, `L122` -> R21...). Duas listas, o mesmo dono, a mesma
coisa, veredictos opostos, e nenhum instrumento que as confronte. E a classe do `BUG-20261023-03`:
*documentacao afirma o contrario da medicao, e a afirmacao nunca e re-medida* -- aqui com uma
variante pior, a auto-referente (ver `known_defects` no mapa: R28 fecha-se correndo o proprio
portao do documento).

O QUE ESTE PORTAO FAZ, E O QUE NAO FAZ. Nao decide quem tem razao sobre o produto -- isso exige o
ecra do dono. Faz tres coisas mecanicas:

  1  POPULACAO. Le as DUAS listas e confere cada uma contra a sua propria contagem declarada.
     Um parser estreito perde linhas em silencio: `[A-D]\\d+` perde o `E1` e da 38 em vez de 39
     (medido; o mutante `drop-row` prova o braco). Por isso a classe e `[A-Z]`.
  2  JUNCAO. Liga cada linha do backlog as mensagens do corpus pelas PALAVRAS DO DONO (citacao
     exacta; recall medido 12/39) e aceita ligacoes declaradas, cada uma verificada por vocabulario
     distintivo contra a mensagem citada. Com isso, `seccoes que reclamam esta linha` e CALCULADO,
     nao escrito por mim.
  3  CONTRADICAO. Uma linha nao fechada cuja reclamacao vive numa seccao `closed` e uma
     CONTRADICAO. O mapa tem de trazer `gap` a dizer o que a evidencia da seccao NAO mede. Sem
     `gap` -> RED. Com `gap` numa linha que nao e contraditoria -> RED (o `gap` nao e decoracao).

E a evidencia do lado fechado tem de ser verificavel: `command` (policy de `closure-evidence-policy.json`,
sem lancar a app), `inspection` (`path:line` que existe) ou `record` (a linha do backlog que contem o
id). Uma citacao morta e RED -- foi assim que a prosa do documento de fecho apodreceu.

    python _main\\\\complaints-reconcile-gate.py            # rc=0 so com o mapa honesto
    python _main\\\\complaints-reconcile-gate.py --neg-arm  # 8 mutantes; rc=1 POR DESENHO
    python _main\\\\complaints-reconcile-gate.py --replay   # re-executa os `closer` de kind=command

LIMITE DECLARADO. `reconciled: closed` com `override` diz *quem* fechou e *quando*, com a saida
citada; nao prova que o dono concorda. O portao nao fecha reclamacoes: proibe que uma contradicao
exista sem nome, e proibe que uma delas se declare fechada sem uma citacao que se possa re-ler.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)

BACKLOG_REL = os.path.join("runs", "TC-20261022-sotto-backlog.md")
CLOSURE_REL = os.path.join(".opencode", "complaints-closure.md")
MAP_REL = os.path.join("_main", "complaints-reconcile.json")
POLICY_REL = os.path.join("_main", "closure-evidence-policy.json")

BACKLOG_ROW = re.compile(r"^\| ([A-Z]\d+) \| (.*?) \| (.*?) \| (.*) \|\s*$")
DECLARED = re.compile(r"(\d+) (FECHADO|PARCIAL|ABERTO|DECIDIDO)")
TOTAL = re.compile(r"(\d+) linhas")
SECTION = re.compile(r"^(R\d+) ")
STATUS = re.compile(r"(?m)^status: (closed|open)$")
FONTE = re.compile(r"fonte `(L\d+)`")
EVIDENCE = re.compile(r"(?m)^evidence: `([^`]+)`")
QUOTE = re.compile(r'"([^"]{8,})"')

STATES = {"FECHADO": "closed", "PARCIAL": "partial", "ABERTO": "open", "DECIDIDO": "decided"}

# A maquinaria do proprio documento de fecho. Uma seccao nao pode fechar uma reclamacao correndo
# o portao que julga o documento que a contem: e o documento a absolver-se.
SELF_CLOSERS = (
    "complaints-closure-gate.py",
    "complaints-closure-build.py",
    "complaints_canon",
    "closure-evidence-replay.py",
    "closure-ledger",
    "build-closure-ledger",
)


# ------------------------------------------------------------------ leitura


def _text(root, rel):
    return io.open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()


def parse_backlog(text):
    rows, declared, total = [], {}, None
    m = TOTAL.search(text)
    if m:
        total = int(m.group(1))
    for line in text.splitlines():
        if line.startswith("**Contagem"):
            for n, st in DECLARED.findall(line):
                declared[st] = declared.get(st, 0) + int(n)
        hit = BACKLOG_ROW.match(line)
        if not hit:
            continue
        iid, words, cell, ev = hit.groups()
        st = re.search(r"\*\*(FECHADO|PARCIAL|ABERTO|DECIDIDO)", cell)
        if not st:
            continue
        rows.append({"id": iid, "state": STATES[st.group(1)], "words": words,
                     "evidence": ev.strip()})
    return rows, declared, total


def parse_closure(text):
    sections = {}
    for block in re.split(r"(?m)^## ", text)[1:]:
        head = block.splitlines()[0]
        hit = SECTION.match(head)
        if not hit:
            continue
        status = STATUS.search(block)
        sections[hit.group(1)] = {
            "title": head,
            "status": status.group(1) if status else "?",
            "fontes": FONTE.findall(block),
            "evidence": EVIDENCE.findall(block),
        }
    return sections


def load_corpus(root):
    sys.path.insert(0, os.path.join(root, "_main"))
    try:
        import complaints_canon as canon  # noqa: WPS433
    finally:
        sys.path.pop(0)
    # A POPULACAO e `complaints()`, nao `load()`: o corpus tem 148 mensagens e so 81 sao
    # reclamacoes (as outras sao directivas, dispatches, ruido). Contar 148 faria o documento de
    # fecho parecer incompleto por 67 linhas que nao sao reclamacoes -- e a primeira versao deste
    # portao fez exactamente isso, apanhada por ele mesmo antes de sair da lane.
    return {m["id"]: m["text"] for m in canon.complaints()}


def norm(text):
    import unicodedata
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower())


# ------------------------------------------------------------------ verificacoes

def check_backlog(rows, declared, total):
    counts = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    inverted = {"closed": "FECHADO", "partial": "PARCIAL", "open": "ABERTO", "decided": "DECIDIDO"}
    bad = ["%s declarado=%d lido=%d" % (inv, declared.get(inv, 0), counts.get(state, 0))
           for state, inv in inverted.items() if declared.get(inv, 0) != counts.get(state, 0)]
    if total is not None and total != len(rows):
        bad.append("total declarado=%d lido=%d" % (total, len(rows)))
    detail = "linhas=%d %s declarados=%s" % (
        len(rows), " ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())),
        ",".join("%s:%d" % (k, v) for k, v in sorted(declared.items())))
    return ("backlog-parsed", not bad, detail if not bad else detail + " | " + "; ".join(bad))


def check_closure(sections, corpus):
    problems = []
    if not sections:
        problems.append("nenhuma seccao R* lida")
    covered = set()
    for sid, sec in sorted(sections.items()):
        if sec["status"] != "closed":
            problems.append("%s status=%s" % (sid, sec["status"]))
        if not sec["fontes"]:
            problems.append("%s sem fonte" % sid)
        missing = [f for f in sec["fontes"] if f not in corpus]
        if missing:
            problems.append("%s cita fonte inexistente %s" % (sid, ",".join(missing[:2])))
        covered |= set(sec["fontes"])
    # A cobertura e do DOCUMENTO, nao so da seccao: uma reclamacao do corpus que nenhuma
    # seccao cita e uma reclamacao que o documento de fecho nao viu -- e o documento diz 81/81.
    uncovered = sorted((set(corpus) - covered), key=lambda x: int(x[1:]))
    if uncovered:
        problems.append("%d reclamacao(oes) do corpus sem seccao: %s"
                        % (len(uncovered), ",".join(uncovered[:4])))
    closed = sum(1 for s in sections.values() if s["status"] == "closed")
    detail = "seccoes=%d closed=%d com_fonte=%d cobertura=%d/%d" % (
        len(sections), closed, sum(1 for s in sections.values() if s["fontes"]),
        len(covered & set(corpus)), len(corpus))
    return ("closure-parsed", not problems, detail if not problems else detail + " | "
            + "; ".join(problems[:4]))


def check_map(rows, payload):
    ids = [r.get("id") for r in payload["rows"]]
    backlog_ids = [r["id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    missing = sorted(set(backlog_ids) - set(ids))
    invented = sorted(set(ids) - set(backlog_ids))
    problems = []
    if dupes:
        problems.append("duplicados: " + ",".join(dupes[:3]))
    if missing:
        problems.append("faltam: " + ",".join(missing[:4]))
    if invented:
        problems.append("inventados: " + ",".join(invented[:4]))
    detail = "linhas=%d mapa=%d" % (len(backlog_ids), len(ids))
    return ("map-covers-population", not problems,
            detail if not problems else detail + " | " + "; ".join(problems))


def check_states(rows, payload):
    backlog = {r["id"]: r["state"] for r in rows}
    bad = []
    for entry in payload["rows"]:
        want = backlog.get(entry.get("id"))
        got = entry.get("reconciled")
        if got not in ("closed", "partial", "open", "decided"):
            bad.append("%s reconciled=%r" % (entry.get("id"), got))
            continue
        if want == got:
            continue
        override = entry.get("override") or {}
        if not all(isinstance(override.get(k), str) and override.get(k).strip()
                   for k in ("reason", "measured_on", "evidence")):
            bad.append("%s backlog=%s mapa=%s sem override(reason,measured_on,evidence)"
                       % (entry.get("id"), want, got))
        elif got != "closed":
            bad.append("%s override so pode fechar, nao abrir (%s->%s)"
                       % (entry.get("id"), want, got))
    detail = "%d estado(s) conferido(s)" % len(payload["rows"])
    return ("map-state-agrees", not bad, detail if not bad else "; ".join(bad[:4]))


def cites_self(command):
    low = command.lower()
    return any(marker in low for marker in SELF_CLOSERS)


def check_evidence(payload, root, dep_root, policy):
    bad, checked = [], 0
    allowed = [h.lower() for h in policy.get("allowed_heads", [])]
    refuse = [s.lower() for s in policy.get("refuse_substrings", [])]
    for entry in payload["rows"]:
        if entry.get("reconciled") != "closed":
            continue
        checked += 1
        ev = entry.get("evidence")
        if not isinstance(ev, dict):
            bad.append("%s sem evidencia" % entry.get("id"))
            continue
        kind = ev.get("kind")
        if kind == "command":
            cmd = str(ev.get("cmd") or "")
            head = cmd.strip().split()[0].lower() if cmd.strip() else ""
            if not cmd or not isinstance(ev.get("expect"), str) or not ev.get("expect"):
                bad.append("%s command sem cmd/expect" % entry["id"])
            elif head not in allowed:
                bad.append("%s command com head proibido %r" % (entry["id"], head))
            elif any(s in cmd.lower() for s in refuse):
                bad.append("%s command recusado pela policy" % entry["id"])
            elif cites_self(cmd):
                bad.append("%s command e a propria maquinaria de fecho" % entry["id"])
            elif not isinstance(ev.get("rc"), int):
                bad.append("%s command sem rc inteiro" % entry["id"])
        elif kind in ("record", "inspection"):
            path = os.path.join(dep_root, str(ev.get("file") or ""))
            line = ev.get("line")
            if not os.path.isfile(path):
                bad.append("%s cita ficheiro inexistente %r" % (entry["id"], ev.get("file")))
                continue
            lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
            if not isinstance(line, int) or not 1 <= line <= len(lines):
                bad.append("%s cita linha %r de %d" % (entry["id"], line, len(lines)))
                continue
            if kind == "record" and ("| %s |" % entry["id"]) not in lines[line - 1]:
                bad.append("%s record L%d nao contem a linha do id" % (entry["id"], line))
        else:
            bad.append("%s kind=%r desconhecido" % (entry.get("id"), kind))
    detail = "%d linha(s) fechada(s) com evidencia verificada" % checked
    return ("closed-has-evidence", not bad, detail if not bad else "; ".join(bad[:4]))


def link_ok(words, text):
    """A ligacao e honesta se as palavras do dono batem no texto: a citacao inteira, ou pelo
    menos DUAS palavras de 5+ letras em comum. Uma palavra so nao liga nada (`sotto`, `painel`)."""
    wn = norm(words)
    if wn.strip() and wn.strip() in text:
        return True
    shared = {w for w in wn.split() if len(w) >= 5} & set(text.split())
    return len(shared) >= 2


def claiming(payload, sections, corpus):
    """{id: [seccoes]} -- calculado das palavras do dono, nunca escrito a mao.

    `decided` fica de FORA: uma decisao do dono nao e uma reclamacao por fechar, logo uma seccao
    de fecho que a mencione nao e uma contradicao.
    """
    fonte_owner = {}
    for sid, sec in sections.items():
        for fonte in sec["fontes"]:
            fonte_owner.setdefault(fonte, []).append(sid)
    out = {}
    for entry in payload["rows"]:
        if entry.get("reconciled") in ("closed", "decided"):
            continue
        ids = [i for i in entry.get("corpus_ids") or [] if i in corpus]
        secs = sorted({s for i in ids for s in fonte_owner.get(i, [])})
        if secs:
            out[entry["id"]] = secs
    return out


def check_contested(payload, sections, corpus):
    contested = claiming(payload, sections, corpus)
    by_id = {e["id"]: e for e in payload["rows"]}
    missing, thin = [], []
    for iid, secs in sorted(contested.items()):
        gap = str(by_id[iid].get("gap") or "").strip()
        if not gap:
            missing.append(iid)
        elif len(gap) < 40 or not any(s in gap for s in secs):
            # Um `gap` tem de NOMEAR a seccao que contradiz e dizer o que ela nao mede: um
            # "inventado" de 9 letras satisfazia a existencia e nao dizia nada. Custou um mutante.
            thin.append("%s (gap=%r)" % (iid, gap[:24]))
    phantom = [e["id"] for e in payload["rows"]
               if str(e.get("gap") or "").strip() and e["id"] not in contested]
    problems = []
    if missing:
        problems.append("contradicao sem `gap`: " + ",".join(missing[:5]))
    if thin:
        problems.append("`gap` que nao nomeia a seccao ou e curto: " + "; ".join(thin[:3]))
    if phantom:
        problems.append("`gap` sem contradicao: " + ",".join(phantom[:5]))
    detail = "contradicoes=%d %s" % (
        len(contested), ",".join("%s->%s" % (i, "/".join(s)) for i, s in sorted(contested.items()))[:110])
    return ("contested-declared", not problems, detail if not problems else detail + " | "
            + "; ".join(problems))


def check_self_closure(payload, sections):
    offenders = {}
    for sid, sec in sections.items():
        for cmd in sec["evidence"]:
            if cites_self(cmd):
                offenders.setdefault(sid, []).append(cmd)
    declared = {d.get("where") for d in payload.get("known_defects") or [] if isinstance(d, dict)}
    undeclared = sorted(set(offenders) - declared)
    problems = []
    if undeclared:
        problems.append("auto-fecho por declarar: " + ",".join(undeclared))
    for where in sorted(declared & set(offenders)):
        entry = next(d for d in payload["known_defects"] if d.get("where") == where)
        if not str(entry.get("defect") or "").strip() or not str(entry.get("owner") or "").strip():
            problems.append("%s declarado sem defect/owner" % where)
    detail = "auto-fecho=%s declarados=%d" % (
        ",".join(sorted(offenders)) or "nenhum", len(declared))
    return ("self-closure-declared", not problems, detail if not problems else detail + " | "
            + "; ".join(problems[:3]))


def check_links(rows, payload, corpus, sections):
    by_id = {r["id"]: r for r in rows}
    fonte_owner = {}
    for sid, sec in sections.items():
        for fonte in sec["fontes"]:
            fonte_owner.setdefault(fonte, []).append(sid)
    bad, linked = [], 0
    for entry in payload["rows"]:
        row = by_id.get(entry.get("id"))
        if row is None:
            continue
        declared = entry.get("corpus_ids") or []
        for cid in declared:
            if cid not in corpus:
                bad.append("%s cita %s, que nao esta no corpus" % (entry["id"], cid))
                continue
            if not link_ok(row["words"], norm(corpus[cid])):
                bad.append("%s cita %s sem duas palavras >=5 letras em comum" % (entry["id"], cid))
        # a citacao exacta e o que o portao SABE; se ela encontra um id, tem de estar declarado
        exact = set()
        for quote in QUOTE.findall(row["words"]):
            q = norm(quote)
            for cid, text in corpus.items():
                if q in norm(text):
                    exact.add(cid)
        notdeclared = sorted(exact - set(declared))
        if notdeclared:
            bad.append("%s: citacao exacta encontra %s e o mapa nao declara"
                       % (entry["id"], ",".join(notdeclared[:3])))
        if declared:
            linked += 1
    detail = "linhas_ligadas=%d/%d" % (linked, len(payload["rows"]))
    return ("link-plausible", not bad, detail if not bad else detail + " | " + "; ".join(bad[:4]))


# ------------------------------------------------------------------ motor


def run_checks(root, dep_root=None):
    dep_root = dep_root or root
    try:
        rows, declared, total = parse_backlog(_text(root, BACKLOG_REL))
        sections = parse_closure(_text(root, CLOSURE_REL))
        payload = json.loads(_text(root, MAP_REL))
        policy = json.loads(_text(root, POLICY_REL))
        corpus = load_corpus(dep_root)
    except (OSError, ValueError, ImportError) as exc:
        return [], "leitura falhou: %s" % exc
    if not rows:
        return [], "o backlog nao produziu uma unica linha"
    if not isinstance(payload.get("rows"), list):
        return [], "o mapa nao tem lista `rows`"
    results = [
        check_backlog(rows, declared, total),
        check_closure(sections, corpus),
        check_map(rows, payload),
        check_states(rows, payload),
        check_evidence(payload, root, dep_root, policy),
        check_contested(payload, sections, corpus),
        check_self_closure(payload, sections),
        check_links(rows, payload, corpus, sections),
    ]
    return results, None


# ------------------------------------------------------------------ mutacoes

TEXT_FILES = (BACKLOG_REL, CLOSURE_REL, MAP_REL, POLICY_REL)


def _tmp_base():
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return base if os.path.isdir(base) else tempfile.gettempdir()


def _copy_texts(root, tmp):
    for rel in TEXT_FILES:
        target = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(target) or tmp, exist_ok=True)
        shutil.copyfile(os.path.join(root, rel), target)


def _rw(path, func):
    text = io.open(path, encoding="utf-8", errors="replace").read()
    io.open(path, "w", encoding="utf-8", newline="\n").write(func(text))


def _map(tmp):
    return os.path.join(tmp, MAP_REL)


def mut_drop_row(tmp, ctx):
    """Apaga uma linha do mapa: a populacao deixa de fechar."""
    def edit(text):
        payload = json.loads(text)
        payload["rows"] = [r for r in payload["rows"] if r["id"] != ctx["closed_id"]]
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


def mut_invent_row(tmp, ctx):
    """Inventa uma linha que o backlog nao tem."""
    def edit(text):
        payload = json.loads(text)
        entry = dict(payload["rows"][0])
        entry["id"] = "Z9"
        payload["rows"] = payload["rows"] + [entry]
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


def mut_flip_state(tmp, ctx):
    """Fecha uma reclamacao do backlog sem override nem evidencia."""
    def edit(text):
        payload = json.loads(text)
        for entry in payload["rows"]:
            if entry["id"] == ctx["open_id"]:
                entry["reconciled"] = "closed"
                entry.pop("blocker", None)
                entry.pop("gap", None)
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


def mut_strip_evidence(tmp, ctx):
    """Tira a evidencia de uma linha fechada."""
    def edit(text):
        payload = json.loads(text)
        for entry in payload["rows"]:
            if entry["id"] == ctx["closed_id"]:
                entry.pop("evidence", None)
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


def mut_dead_citation(tmp, ctx):
    """Aponta a citacao para uma linha que nao existe."""
    def edit(text):
        payload = json.loads(text)
        for entry in payload["rows"]:
            if entry["id"] == ctx["closed_id"] and entry.get("evidence", {}).get("kind") == "record":
                entry["evidence"]["line"] = 10 ** 6
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


def mut_hide_gap(tmp, ctx):
    """Apaga o `gap` de uma linha contraditoria: a contradicao volta a ser silenciosa."""
    def edit(text):
        payload = json.loads(text)
        for entry in payload["rows"]:
            if entry["id"] == ctx["contested_id"]:
                entry.pop("gap", None)
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


def mut_phantom_gap(tmp, ctx):
    """Poe um `gap` numa linha que nao e contraditoria."""
    def edit(text):
        payload = json.loads(text)
        for entry in payload["rows"]:
            if entry["id"] == ctx["closed_id"]:
                entry["gap"] = "inventado"
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


def mut_undeclare_self(tmp, ctx):
    """Tira o auto-fecho dos defeitos declarados."""
    def edit(text):
        payload = json.loads(text)
        payload["known_defects"] = []
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


def mut_drop_fonte(tmp, ctx):
    """Apaga a unica fonte de uma seccao de um so: a reclamacao fica sem cobertura."""
    def edit(text):
        blocks = re.split(r"(?m)^(## R\d+ .*)$", text)
        # blocks: [pre, head1, body1, head2, body2, ...]
        for i in range(1, len(blocks), 2):
            body = blocks[i + 1]
            fontes = FONTE.findall(body)
            if len(fontes) != 1:
                continue
            kept = [ln for ln in body.splitlines(True) if not ln.startswith("- fonte `")]
            if len(kept) == len(body.splitlines(True)):
                continue
            blocks[i + 1] = "".join(kept)
            return "".join(blocks)
        raise RuntimeError("nenhuma seccao com uma unica fonte")
    _rw(os.path.join(tmp, CLOSURE_REL), edit)


def mut_thin_gap(tmp, ctx):
    """Troca um `gap` por uma palavra: a existencia fica, a informacao nao."""
    def edit(text):
        payload = json.loads(text)
        for entry in payload["rows"]:
            if entry["id"] == ctx["contested_id"]:
                entry["gap"] = "inventado"
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _rw(_map(tmp), edit)


MUTATIONS = (
    ("drop-row", mut_drop_row, "map-covers-population"),
    ("invent-row", mut_invent_row, "map-covers-population"),
    ("flip-state", mut_flip_state, "map-state-agrees"),
    ("strip-evidence", mut_strip_evidence, "closed-has-evidence"),
    ("dead-citation", mut_dead_citation, "closed-has-evidence"),
    ("hide-gap", mut_hide_gap, "contested-declared"),
    ("thin-gap", mut_thin_gap, "contested-declared"),
    ("phantom-gap", mut_phantom_gap, "contested-declared"),
    ("undeclare-self-closure", mut_undeclare_self, "self-closure-declared"),
    ("drop-fonte", mut_drop_fonte, "closure-parsed"),
)


def _context(root):
    rows, _, _ = parse_backlog(_text(root, BACKLOG_REL))
    payload = json.loads(_text(root, MAP_REL))
    sections = parse_closure(_text(root, CLOSURE_REL))
    corpus = load_corpus(root)
    contested = claiming(payload, sections, corpus)
    closed = [e["id"] for e in payload["rows"] if e.get("reconciled") == "closed"
              and (e.get("evidence") or {}).get("kind") == "record"]
    open_uncontested = [e["id"] for e in payload["rows"]
                        if e.get("reconciled") != "closed" and e["id"] not in contested]
    if not contested or not closed or not open_uncontested:
        raise RuntimeError("o repo real nao oferece as linhas de que os mutantes precisam")
    return {"closed_id": closed[0], "contested_id": sorted(contested)[0],
            "open_id": open_uncontested[0]}


def run_mutation(root, entry):
    name, mutate, expected = entry
    tmp = tempfile.mkdtemp(prefix="complaints-reconcile-", dir=_tmp_base())
    try:
        if os.path.realpath(tmp).startswith(os.path.realpath(root) + os.sep):
            raise RuntimeError("directorio temporario dentro da raiz do repo")
        _copy_texts(root, tmp)
        ctx = _context(root)
        base, error = run_checks(tmp, dep_root=root)
        if error is not None:
            return "COPY-BROKEN", [], error, expected
        broken = [n for n, ok, _ in base if not ok]
        if broken:
            return "COPY-BROKEN", base, "a copia intacta ja falha: %s" % ", ".join(broken), expected
        mutate(tmp, ctx)
        mutated, error = run_checks(tmp, dep_root=root)
        if error is not None:
            return "COPY-BROKEN", mutated or [], "leitura falhou apos a mutacao: %s" % error, expected
        refused = [n for n, ok, _ in mutated if not ok]
        if expected not in refused:
            return "NEG-ARM FAIL", mutated, "o check NOMEADO (%s) nao recusou; recusaram: %s" % (
                expected, ", ".join(refused) or "nenhum"), expected
        return "NEG-ARM PASS", mutated, "recusou por: %s" % ", ".join(refused), expected
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ replay opt-in


def replay(root, payload, policy):
    refuse = [s.lower() for s in policy.get("refuse_substrings", [])]
    allowed = [h.lower() for h in policy.get("allowed_heads", [])]
    ran = failed = skipped = 0
    for entry in payload["rows"]:
        ev = entry.get("evidence") or {}
        if entry.get("reconciled") != "closed" or ev.get("kind") != "command":
            continue
        cmd = str(ev.get("cmd"))
        head = cmd.strip().split()[0].lower()
        if head not in allowed or any(s in cmd.lower() for s in refuse) or cites_self(cmd):
            skipped += 1
            print("REPLAY SKIP %-4s %s (policy)" % (entry["id"], cmd))
            continue
        proc = subprocess.run(cmd, cwd=root, shell=False, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=900)
        out = proc.stdout.decode("utf-8", "replace")
        ran += 1
        ok = proc.returncode == ev.get("rc") and str(ev.get("expect")) in out
        if not ok:
            failed += 1
        print("REPLAY %-4s %s rc=%d esperado=%s literal=%s"
              % ("PASS" if ok else "FAIL", entry["id"], proc.returncode, ev.get("rc"),
                 "achado" if str(ev.get("expect")) in out else "AUSENTE"))
    print("REPLAY-VERDICT %s ran=%d failed=%d skipped=%d"
          % ("PASS" if failed == 0 else "FAIL", ran, failed, skipped))
    return 0 if failed == 0 else 1


# ------------------------------------------------------------------ CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description="reconcilia as duas listas de reclamacoes")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--neg-arm", action="store_true", help="todos os mutantes; rc=1 POR DESENHO")
    parser.add_argument("--mutation", choices=[m[0] for m in MUTATIONS])
    parser.add_argument("--list-mutations", action="store_true")
    parser.add_argument("--replay", action="store_true", help="re-executa os closer de kind=command")
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
    for rel in (BACKLOG_REL, CLOSURE_REL, MAP_REL):
        if not os.path.isfile(os.path.join(root, rel)):
            print("COMPLAINTS-RECONCILE: NO-VERDICT ausente: %s" % rel)
            return 2

    if args.neg_arm or args.mutation:
        selected = [m for m in MUTATIONS if args.mutation == m[0]] or list(MUTATIONS)
        outcomes = []
        for entry in selected:
            try:
                status, results, detail, expected = run_mutation(root, entry)
            except (OSError, RuntimeError, ValueError) as exc:
                print("MUTATION %-24s ERROR  %s" % (entry[0], exc))
                return 2
            print("MUTATION %-24s %s  [esperado: %s] %s" % (entry[0], status, expected, detail))
            for check, ok, check_detail in results:
                print("  mut-check %-22s %s  %s" % (check, "PASS" if ok else "FAIL", check_detail))
            outcomes.append(status)
        if "COPY-BROKEN" in outcomes:
            print("COMPLAINTS-RECONCILE NO-VERDICT copy-broken mutations=%d" % len(outcomes))
            return 2
        failed = sum(1 for s in outcomes if s != "NEG-ARM PASS")
        print("NEG-ARM %s mutations=%d named-arm-fail=%d"
              % ("PASS" if failed == 0 else "FAIL", len(outcomes), failed))
        return 1

    results, error = run_checks(root)
    if error is not None:
        print("COMPLAINTS-RECONCILE: NO-VERDICT %s" % error)
        return 2
    for name, ok, detail in results:
        print("CHECK %-22s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
    fail = sum(1 for _, ok, _ in results if not ok)

    if args.replay:
        payload = json.loads(_text(root, MAP_REL))
        policy = json.loads(_text(root, POLICY_REL))
        return replay(root, payload, policy)

    payload = json.loads(_text(root, MAP_REL))
    counts = {}
    for entry in payload["rows"]:
        counts[entry["reconciled"]] = counts.get(entry["reconciled"], 0) + 1
    print("SUMMARY lines=%d %s contradicoes=%d"
          % (len(payload["rows"]),
             " ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())),
             len(claiming(payload, parse_closure(_text(root, CLOSURE_REL)), load_corpus(root)))))
    print("COMPLAINTS-RECONCILE %s checks=%d fail=%d"
          % ("PASS" if fail == 0 else "FAIL", len(results), fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
